# SDK Spec Expansion (PR-154) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring all four hand-written Mechbase SDKs up to the PR-154 API spec — registry CRUD, batch measurements, measurement file attach, richer point-history pagination (all four languages), plus a maintnode device client (Python + Go only).

**Architecture:** Each client keeps its existing shape: a top-level client → installation handle → per-resource objects, over a thin HTTP layer. We extend models, add write methods to the registry resources, add two new registry resources (sections, zones), add batch/file/iter methods to measurements, and add a separate token-less `MaintNode` client (Python + Go). No codegen — hand-written to match `openapi.json`.

**Tech Stack:** Python (httpx + respx tests), Go (net/http + httptest tests), Swift (URLSession + URLProtocol stub tests), Kotlin (OkHttp + MockWebServer tests).

**Spec source:** `https://pr-154.mechbase.io/api/openapi.json`, already saved in the repo as `openapi.new.json` (Phase 0 promotes it to `openapi.json`).

**Out of scope:** `POST /api/auth/login`, `GET .../legacy-redirects`, any codegen. See `docs/superpowers/specs/2026-06-16-sdk-spec-expansion-design.md`.

---

## Shared Reference — endpoints, fields, error codes

These tables are the single source of truth. Every language phase below refers back here instead of repeating the lists. The four registry resources are **structurally identical** — the only differences are the path segment, the id parameter name, and the input/output field sets.

### Registry endpoints (installation-scoped, base `/api/installations/{iid}`)

| Resource | collection path | item path | id param |
|---|---|---|---|
| assets | `/assets` | `/assets/{asset_id}` | `asset_id` (int) |
| measurement-points | `/measurement-points` | `/measurement-points/{point_id}` | `point_id` (int) |
| sections | `/sections` | `/sections/{section_id}` | `section_id` (int) |
| zones | `/zones` | `/zones/{zone_id}` | `zone_id` (int) |

Each resource supports: `GET collection` (list, offset page `{items,total,limit,offset}`), `GET item` (one), `POST collection` (create → 201), `PUT collection` (upsert → 200/201), `PATCH item` (update → 200), `DELETE item?cascade=<bool>` (→ `{deleted,uuid}`). All write bodies omit `null`/unset fields so PATCH stays partial. (assets + measurement-points already have list/get; sections + zones are brand new resources.)

### Input field sets (all optional; only non-null serialized)

- **AssetInput:** `name, external_id, section_id, section_external_id, zone_id, zone_external_id, equipment_type, machine_class`
- **PointInput:** `name, external_id, asset_id, asset_external_id, transducer_type, measurement_unit_code, location, body_segment, body_angle, machine_class`
- **SectionInput:** `name, external_id`
- **ZoneInput:** `name, external_id, section_id, section_external_id`

`section_id`/`asset_id`/`zone_id` are ints; `body_segment`/`body_angle` are ints; everything else is a string.

### Output models (response shapes)

- **Asset** (was: uuid, asset_id, name, zone_id, machine_class, status) **adds** `section_id: int?`, `equipment_type: string`, `external_id: string?`
- **MeasurementPoint** **adds** `external_id: string?`
- **Measurement** **adds** `external_id: string?`
- **Section** (new): `uuid, section_id: int?, name, external_id: string?`
- **Zone** (new): `uuid, zone_id: int?, name, section_id: int?, external_id: string?`
- **DeleteResult** (new): `deleted: bool, uuid: string`

### Batch measurements — `POST /api/installations/{iid}/measurements/batch/`

- Request `MeasurementBatchIn`: `{ "items": [MeasurementInput] }`
- **MeasurementInput:** `measurement_point_id: int?`, `measurement_point_external_id: string?` (supply one), `data: object` (required), `notes: string?`, `session_id: string?`, `timestamp: string?`, `external_id: string?`
- Response `MeasurementBatchOut`: `created: int, duplicates: int, errors: int, results: [BatchItemResult]`
- **BatchItemResult:** `index: int, status: string, measurement_point_id: int?, point_sequence: int?, uuid: string?, external_id: string?, detail: string?`

### Measurement file attach — `POST /api/installations/{iid}/measurements/{measurement_uuid}/files/`

- multipart/form-data, single field `file` (binary). Returns `FileAttachment`: `uuid, name, kind, file_url, created_at`.

### Point history — `GET /api/installations/{iid}/measurement-points/{point_id}/measurements/`

- Query: `limit, offset, created_from, created_to, cursor`. Returns an **offset page** (`{items,total,limit,offset}`) normally, or a **cursor page** (`{items, next_cursor}`) when `cursor` is supplied. `list_for_point` uses offset mode; `iter_for_point` drives cursor mode (start with `cursor=""`, follow `next_cursor` until null/absent).

### Maintnode device API (Python + Go only) — base `/api/maintnode/{node_uuid}`, **no auth header**

| op | method + path | body | returns |
|---|---|---|---|
| config | `GET /config/` | — | `string` (raw config blob) |
| heartbeat | `POST /heartbeat/` | `{balena_uuid, services}` | object (dict) |
| push measurements | `POST /measurements/` | `{measurements: [MaintNodeMeasurementInput]}` | `[MeasurementResult]` |
| add file | `POST /measurements/{measurement_uuid}/file/` | multipart field `file` | object (dict) |

- **MaintNodeMeasurementInput:** `mapping_uuid: string` (required), `data: object` (required), `timestamp: string?`, `local_uuid: string?`
- **MeasurementResult:** `mapping_uuid, ok: bool, measurement_uuid: string?, local_uuid: string, error: string`

### Error mapping (all clients)

Add to the existing 401/403→auth, 404→not-found, 422→validation map:
- **409 → ConflictError** (duplicate `external_id`, etc.)
- **413 → PayloadTooLargeError** (file too large)

Error body is unchanged: `{"detail": "..."}`. New error types subclass the existing base so existing catch-all code is unaffected.

### Version bump

Every client moves `0.1 → 0.2`: User-Agent strings (`mechbase-<lang>/0.2`), `python/pyproject.toml` `version`, `kotlin/build.gradle.kts` `version`. The Go and Kotlin tests assert the User-Agent string — update those assertions too.

---

## Phase 0 — Spec sync

### Task 0.1: Promote the new OpenAPI spec

**Files:**
- Modify: `openapi.json` (overwrite)
- Delete: `openapi.new.json`

- [ ] **Step 1: Replace the committed spec and remove the scratch copy**

Run:
```bash
cd /Users/tsangiotis/dev/mechbase/mechbase-sdk
mv openapi.new.json openapi.json
python3 -c "import json; d=json.load(open('openapi.json')); print('paths:', len(d['paths']))"
```
Expected: `paths: 30`

- [ ] **Step 2: Commit**

```bash
git add openapi.json
git rm --cached openapi.new.json 2>/dev/null; true
git commit -m "chore: sync openapi.json to PR-154 spec"
```

---

## Phase 1 — Python (reference implementation)

Work dir: `python/`. Run tests with `cd python && .venv/bin/pytest -q` (the repo ships a `.venv`; if missing, `uv sync` or `pip install -e '.[dev]'`).

### Task 1.1: Errors — add ConflictError + PayloadTooLargeError, make token optional

**Files:**
- Modify: `python/src/mechbase/errors.py`
- Modify: `python/src/mechbase/_http.py`
- Modify: `python/src/mechbase/__init__.py`
- Test: `python/tests/test_registry.py` (new)

- [ ] **Step 1: Write the failing test**

Create `python/tests/test_registry.py`:
```python
"""Offline tests for registry CRUD, batch, files, history, errors."""
from __future__ import annotations

import httpx
import pytest
import respx

from mechbase import ConflictError, Mechbase, PayloadTooLargeError

BASE = "https://example.test"


@pytest.fixture
def client():
    c = Mechbase(token="tok", base_url=BASE)
    yield c
    c.close()


@respx.mock
def test_conflict_error(client):
    respx.post(f"{BASE}/api/installations/2012/assets").mock(
        return_value=httpx.Response(409, json={"detail": "duplicate external_id"})
    )
    with pytest.raises(ConflictError):
        client.for_installation(2012).assets.create(name="Pump", external_id="P-1")


@respx.mock
def test_payload_too_large_error(client):
    respx.post(
        f"{BASE}/api/installations/2012/measurements/m-1/files/"
    ).mock(return_value=httpx.Response(413, json={"detail": "too big"}))
    with pytest.raises(PayloadTooLargeError):
        client.for_installation(2012).measurements.add_file("m-1", file=b"x")
```

- [ ] **Step 2: Run it — expect failure**

Run: `cd python && .venv/bin/pytest tests/test_registry.py -q`
Expected: FAIL — `ImportError: cannot import name 'ConflictError'`.

- [ ] **Step 3: Add the error classes**

Append to `python/src/mechbase/errors.py`:
```python
class ConflictError(MechbaseError):
    """409."""


class PayloadTooLargeError(MechbaseError):
    """413."""
```

- [ ] **Step 4: Map the new statuses and allow a tokenless client**

In `python/src/mechbase/_http.py`, change the imports and `__init__` and `_handle`:
```python
from .errors import (
    AuthError,
    ConflictError,
    MechbaseError,
    NotFoundError,
    PayloadTooLargeError,
    ValidationError,
)
```
Replace `__init__` so `token` is optional and the header is conditional:
```python
    def __init__(self, *, token: str | None, base_url: str, timeout: float = 30.0):
        headers = {
            "User-Agent": "mechbase-python/0.2",
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
        )
```
In `_handle`, add before the final `raise`:
```python
        if response.status_code == 409:
            raise ConflictError(message, status=response.status_code, body=body)
        if response.status_code == 413:
            raise PayloadTooLargeError(message, status=response.status_code, body=body)
```

- [ ] **Step 5: Export the new errors**

In `python/src/mechbase/__init__.py` add `ConflictError, PayloadTooLargeError` to the import from `.errors` and to `__all__`.

- [ ] **Step 6: Run — the file test still needs `add_file`/`create`; isolate the error tests**

Run: `cd python && .venv/bin/pytest tests/test_registry.py::test_conflict_error -q`
Expected: still FAIL — `AttributeError: 'Assets' object has no attribute 'create'` (errors import now resolves). This proves error wiring works; the create/add_file methods come in 1.3/1.4. Do not commit yet — continue to 1.2.

### Task 1.2: Models — extend and add registry/batch/file/maintnode models

**Files:**
- Modify: `python/src/mechbase/models.py`

- [ ] **Step 1: Extend `Asset`** (replace the class) per the Shared Reference output models:
```python
@dataclass
class Asset:
    uuid: str
    asset_id: int | None
    name: str
    section_id: int | None
    zone_id: int | None
    machine_class: str
    equipment_type: str
    status: int
    external_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Asset":
        d = dict(d)
        return cls(
            uuid=d.pop("uuid"),
            asset_id=d.pop("asset_id", None),
            name=d.pop("name"),
            section_id=d.pop("section_id", None),
            zone_id=d.pop("zone_id", None),
            machine_class=d.pop("machine_class", ""),
            equipment_type=d.pop("equipment_type", ""),
            status=d.pop("status"),
            external_id=d.pop("external_id", None),
            extra=d,
        )
```

- [ ] **Step 2: Add `external_id` to `MeasurementPoint`** — add field `external_id: str | None = None` after `status`, and in `from_dict` add `external_id=d.get("external_id")`.

- [ ] **Step 3: Add `external_id` to `Measurement`** — add field `external_id: str | None = None` (before `file_url`) and `external_id=d.get("external_id")` in `from_dict`.

- [ ] **Step 4: Append new dataclasses** to `models.py`:
```python
@dataclass
class Section:
    uuid: str
    section_id: int | None
    name: str
    external_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Section":
        return cls(
            uuid=d["uuid"],
            section_id=d.get("section_id"),
            name=d["name"],
            external_id=d.get("external_id"),
        )


@dataclass
class Zone:
    uuid: str
    zone_id: int | None
    name: str
    section_id: int | None = None
    external_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Zone":
        return cls(
            uuid=d["uuid"],
            zone_id=d.get("zone_id"),
            name=d["name"],
            section_id=d.get("section_id"),
            external_id=d.get("external_id"),
        )


@dataclass
class DeleteResult:
    deleted: bool
    uuid: str

    @classmethod
    def from_dict(cls, d: dict) -> "DeleteResult":
        return cls(deleted=d["deleted"], uuid=d["uuid"])


@dataclass
class BatchItemResult:
    index: int
    status: str
    measurement_point_id: int | None = None
    point_sequence: int | None = None
    uuid: str | None = None
    external_id: str | None = None
    detail: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "BatchItemResult":
        return cls(
            index=d["index"],
            status=d["status"],
            measurement_point_id=d.get("measurement_point_id"),
            point_sequence=d.get("point_sequence"),
            uuid=d.get("uuid"),
            external_id=d.get("external_id"),
            detail=d.get("detail"),
        )


@dataclass
class BatchResult:
    created: int
    duplicates: int
    errors: int
    results: list[BatchItemResult]

    @classmethod
    def from_dict(cls, d: dict) -> "BatchResult":
        return cls(
            created=d["created"],
            duplicates=d["duplicates"],
            errors=d["errors"],
            results=[BatchItemResult.from_dict(r) for r in d["results"]],
        )


@dataclass
class FileAttachment:
    uuid: str
    name: str
    kind: str
    file_url: str
    created_at: str

    @classmethod
    def from_dict(cls, d: dict) -> "FileAttachment":
        return cls(
            uuid=d["uuid"],
            name=d["name"],
            kind=d["kind"],
            file_url=d["file_url"],
            created_at=d["created_at"],
        )


@dataclass
class MeasurementResult:
    mapping_uuid: str
    ok: bool
    measurement_uuid: str | None = None
    local_uuid: str = ""
    error: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "MeasurementResult":
        return cls(
            mapping_uuid=d["mapping_uuid"],
            ok=d["ok"],
            measurement_uuid=d.get("measurement_uuid"),
            local_uuid=d.get("local_uuid", ""),
            error=d.get("error", ""),
        )
```

- [ ] **Step 5: Run the existing suite to confirm no regression**

Run: `cd python && .venv/bin/pytest tests/test_client.py -q`
Expected: PASS (4 tests). The `test_list_assets` still works because `Asset.from_dict` tolerates the old payload (new fields default).

### Task 1.3: Registry CRUD resources

**Files:**
- Modify: `python/src/mechbase/resources/_base.py` (add `_clean` helper)
- Modify: `python/src/mechbase/resources/registry.py` (write methods + new Sections/Zones)
- Modify: `python/src/mechbase/client.py` (wire sections/zones into the handle)
- Test: `python/tests/test_registry.py`

- [ ] **Step 1: Write failing tests** — append to `python/tests/test_registry.py`:
```python
@respx.mock
def test_asset_crud_roundtrip(client):
    respx.post(f"{BASE}/api/installations/2012/assets").mock(
        return_value=httpx.Response(201, json={
            "uuid": "a-1", "asset_id": 7, "name": "Pump 7", "section_id": 3,
            "zone_id": 2, "machine_class": "II", "equipment_type": "pump",
            "status": 1, "external_id": "P-7"})
    )
    respx.put(f"{BASE}/api/installations/2012/assets").mock(
        return_value=httpx.Response(200, json={
            "uuid": "a-1", "asset_id": 7, "name": "Pump 7b", "section_id": 3,
            "zone_id": 2, "machine_class": "II", "equipment_type": "pump",
            "status": 1, "external_id": "P-7"})
    )
    respx.patch(f"{BASE}/api/installations/2012/assets/7").mock(
        return_value=httpx.Response(200, json={
            "uuid": "a-1", "asset_id": 7, "name": "Pump 7c", "section_id": 3,
            "zone_id": 2, "machine_class": "II", "equipment_type": "pump",
            "status": 1, "external_id": "P-7"})
    )
    respx.delete(f"{BASE}/api/installations/2012/assets/7").mock(
        return_value=httpx.Response(200, json={"deleted": True, "uuid": "a-1"})
    )
    assets = client.for_installation(2012).assets
    created = assets.create(name="Pump 7", external_id="P-7", section_external_id="S-1")
    assert created.asset_id == 7 and created.equipment_type == "pump"
    upserted = assets.upsert(external_id="P-7", name="Pump 7b")
    assert upserted.name == "Pump 7b"
    updated = assets.update(7, name="Pump 7c")
    assert updated.name == "Pump 7c"
    deleted = assets.delete(7, cascade=True)
    assert deleted.deleted is True and deleted.uuid == "a-1"


@respx.mock
def test_sections_and_zones(client):
    respx.get(f"{BASE}/api/installations/2012/sections").mock(
        return_value=httpx.Response(200, json={"items": [
            {"uuid": "s-1", "section_id": 3, "name": "Hall A", "external_id": "S-1"}],
            "total": 1, "limit": 50, "offset": 0})
    )
    respx.post(f"{BASE}/api/installations/2012/zones").mock(
        return_value=httpx.Response(201, json={
            "uuid": "z-1", "zone_id": 9, "name": "Zone 9",
            "section_id": 3, "external_id": "Z-9"})
    )
    inst = client.for_installation(2012)
    sections = inst.sections.list()
    assert sections[0].name == "Hall A" and sections[0].section_id == 3
    zone = inst.zones.create(name="Zone 9", external_id="Z-9", section_external_id="S-1")
    assert zone.zone_id == 9 and zone.section_id == 3
```

- [ ] **Step 2: Run — expect failure**

Run: `cd python && .venv/bin/pytest tests/test_registry.py::test_asset_crud_roundtrip -q`
Expected: FAIL — `AttributeError: 'Assets' object has no attribute 'create'`.

- [ ] **Step 3: Add `_clean` helper** to `python/src/mechbase/resources/_base.py`:
```python
def _clean(d: dict) -> dict:
    """Drop keys whose value is None (keeps PATCH partial)."""
    return {k: v for k, v in d.items() if v is not None}
```

- [ ] **Step 4: Rewrite `python/src/mechbase/resources/registry.py`** with write methods and the two new resources:
```python
from __future__ import annotations

from ..models import Asset, DeleteResult, MeasurementPoint, Section, Zone
from ._base import InstallationScoped, _clean, _paginated


class Assets(InstallationScoped):
    def list(self, *, q: str = "", zone_id: int | None = None, limit: int = 50, offset: int = 0) -> list[Asset]:
        return _paginated(
            self._http, self._path("/assets"),
            params={"q": q, "zone_id": zone_id, "limit": limit, "offset": offset},
            parse=Asset.from_dict,
        )

    def get(self, asset_id: int) -> Asset:
        return Asset.from_dict(self._http.request("GET", self._path(f"/assets/{asset_id}")))

    def create(self, *, name: str | None = None, external_id: str | None = None,
               section_id: int | None = None, section_external_id: str | None = None,
               zone_id: int | None = None, zone_external_id: str | None = None,
               equipment_type: str | None = None, machine_class: str | None = None) -> Asset:
        return Asset.from_dict(self._http.request("POST", self._path("/assets"), json=_clean(locals_no_self(locals()))))

    def upsert(self, *, name: str | None = None, external_id: str | None = None,
               section_id: int | None = None, section_external_id: str | None = None,
               zone_id: int | None = None, zone_external_id: str | None = None,
               equipment_type: str | None = None, machine_class: str | None = None) -> Asset:
        return Asset.from_dict(self._http.request("PUT", self._path("/assets"), json=_clean(locals_no_self(locals()))))

    def update(self, asset_id: int, *, name: str | None = None, external_id: str | None = None,
               section_id: int | None = None, section_external_id: str | None = None,
               zone_id: int | None = None, zone_external_id: str | None = None,
               equipment_type: str | None = None, machine_class: str | None = None) -> Asset:
        body = _clean({k: v for k, v in locals().items() if k not in ("self", "asset_id")})
        return Asset.from_dict(self._http.request("PATCH", self._path(f"/assets/{asset_id}"), json=body))

    def delete(self, asset_id: int, *, cascade: bool = False) -> DeleteResult:
        params = {"cascade": "true"} if cascade else None
        return DeleteResult.from_dict(self._http.request("DELETE", self._path(f"/assets/{asset_id}"), params=params))


class MeasurementPoints(InstallationScoped):
    def list(self, *, q: str = "", asset_id: int | None = None, transducer_type: str = "",
             limit: int = 50, offset: int = 0) -> list[MeasurementPoint]:
        return _paginated(
            self._http, self._path("/measurement-points"),
            params={"q": q, "asset_id": asset_id, "transducer_type": transducer_type,
                    "limit": limit, "offset": offset},
            parse=MeasurementPoint.from_dict,
        )

    def get(self, point_id: int) -> MeasurementPoint:
        return MeasurementPoint.from_dict(self._http.request("GET", self._path(f"/measurement-points/{point_id}")))

    def create(self, *, name: str | None = None, external_id: str | None = None,
               asset_id: int | None = None, asset_external_id: str | None = None,
               transducer_type: str | None = None, measurement_unit_code: str | None = None,
               location: str | None = None, body_segment: int | None = None,
               body_angle: int | None = None, machine_class: str | None = None) -> MeasurementPoint:
        return MeasurementPoint.from_dict(self._http.request("POST", self._path("/measurement-points"), json=_clean(locals_no_self(locals()))))

    def upsert(self, *, name: str | None = None, external_id: str | None = None,
               asset_id: int | None = None, asset_external_id: str | None = None,
               transducer_type: str | None = None, measurement_unit_code: str | None = None,
               location: str | None = None, body_segment: int | None = None,
               body_angle: int | None = None, machine_class: str | None = None) -> MeasurementPoint:
        return MeasurementPoint.from_dict(self._http.request("PUT", self._path("/measurement-points"), json=_clean(locals_no_self(locals()))))

    def update(self, point_id: int, *, name: str | None = None, external_id: str | None = None,
               asset_id: int | None = None, asset_external_id: str | None = None,
               transducer_type: str | None = None, measurement_unit_code: str | None = None,
               location: str | None = None, body_segment: int | None = None,
               body_angle: int | None = None, machine_class: str | None = None) -> MeasurementPoint:
        body = _clean({k: v for k, v in locals().items() if k not in ("self", "point_id")})
        return MeasurementPoint.from_dict(self._http.request("PATCH", self._path(f"/measurement-points/{point_id}"), json=body))

    def delete(self, point_id: int, *, cascade: bool = False) -> DeleteResult:
        params = {"cascade": "true"} if cascade else None
        return DeleteResult.from_dict(self._http.request("DELETE", self._path(f"/measurement-points/{point_id}"), params=params))


class Sections(InstallationScoped):
    def list(self, *, q: str = "", limit: int = 50, offset: int = 0) -> list[Section]:
        return _paginated(self._http, self._path("/sections"),
                          params={"q": q, "limit": limit, "offset": offset},
                          parse=Section.from_dict)

    def get(self, section_id: int) -> Section:
        return Section.from_dict(self._http.request("GET", self._path(f"/sections/{section_id}")))

    def create(self, *, name: str | None = None, external_id: str | None = None) -> Section:
        return Section.from_dict(self._http.request("POST", self._path("/sections"), json=_clean(locals_no_self(locals()))))

    def upsert(self, *, name: str | None = None, external_id: str | None = None) -> Section:
        return Section.from_dict(self._http.request("PUT", self._path("/sections"), json=_clean(locals_no_self(locals()))))

    def update(self, section_id: int, *, name: str | None = None, external_id: str | None = None) -> Section:
        body = _clean({k: v for k, v in locals().items() if k not in ("self", "section_id")})
        return Section.from_dict(self._http.request("PATCH", self._path(f"/sections/{section_id}"), json=body))

    def delete(self, section_id: int, *, cascade: bool = False) -> DeleteResult:
        params = {"cascade": "true"} if cascade else None
        return DeleteResult.from_dict(self._http.request("DELETE", self._path(f"/sections/{section_id}"), params=params))


class Zones(InstallationScoped):
    def list(self, *, q: str = "", section_id: int | None = None, limit: int = 50, offset: int = 0) -> list[Zone]:
        return _paginated(self._http, self._path("/zones"),
                          params={"q": q, "section_id": section_id, "limit": limit, "offset": offset},
                          parse=Zone.from_dict)

    def get(self, zone_id: int) -> Zone:
        return Zone.from_dict(self._http.request("GET", self._path(f"/zones/{zone_id}")))

    def create(self, *, name: str | None = None, external_id: str | None = None,
               section_id: int | None = None, section_external_id: str | None = None) -> Zone:
        return Zone.from_dict(self._http.request("POST", self._path("/zones"), json=_clean(locals_no_self(locals()))))

    def upsert(self, *, name: str | None = None, external_id: str | None = None,
               section_id: int | None = None, section_external_id: str | None = None) -> Zone:
        return Zone.from_dict(self._http.request("PUT", self._path("/zones"), json=_clean(locals_no_self(locals()))))

    def update(self, zone_id: int, *, name: str | None = None, external_id: str | None = None,
               section_id: int | None = None, section_external_id: str | None = None) -> Zone:
        body = _clean({k: v for k, v in locals().items() if k not in ("self", "zone_id")})
        return Zone.from_dict(self._http.request("PATCH", self._path(f"/zones/{zone_id}"), json=body))

    def delete(self, zone_id: int, *, cascade: bool = False) -> DeleteResult:
        params = {"cascade": "true"} if cascade else None
        return DeleteResult.from_dict(self._http.request("DELETE", self._path(f"/zones/{zone_id}"), params=params))


def locals_no_self(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "self"}
```

- [ ] **Step 5: Wire sections/zones into the handle** — in `python/src/mechbase/client.py`, update the import to `from .resources.registry import Assets, MeasurementPoints, Sections, Zones` and add to `InstallationHandle.__init__`:
```python
        self.sections = Sections(http, installation_id)
        self.zones = Zones(http, installation_id)
```

- [ ] **Step 6: Run the registry tests**

Run: `cd python && .venv/bin/pytest tests/test_registry.py::test_asset_crud_roundtrip tests/test_registry.py::test_sections_and_zones tests/test_registry.py::test_conflict_error -q`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**
```bash
git add python/
git commit -m "feat(py): registry CRUD (assets, points, sections, zones) + conflict error"
```

### Task 1.4: Batch, file attach, and cursor history

**Files:**
- Modify: `python/src/mechbase/resources/measurements.py`
- Test: `python/tests/test_registry.py`

- [ ] **Step 1: Write failing tests** — append:
```python
@respx.mock
def test_create_batch(client):
    respx.post(f"{BASE}/api/installations/2012/measurements/batch/").mock(
        return_value=httpx.Response(200, json={
            "created": 1, "duplicates": 1, "errors": 0,
            "results": [
                {"index": 0, "status": "created", "measurement_point_id": 1,
                 "point_sequence": 5, "uuid": "m-1", "external_id": "E-0", "detail": None},
                {"index": 1, "status": "duplicate", "measurement_point_id": 1,
                 "point_sequence": 5, "uuid": "m-1", "external_id": "E-1", "detail": None},
            ]})
    )
    res = client.for_installation(2012).measurements.create_batch([
        {"measurement_point_id": 1, "data": {"rms": 2.3}, "external_id": "E-0"},
        {"measurement_point_external_id": "PUMP-DE", "data": {"rms": 2.4}, "external_id": "E-1"},
    ])
    assert res.created == 1 and res.duplicates == 1
    assert res.results[0].status == "created"


@respx.mock
def test_add_file(client):
    respx.post(f"{BASE}/api/installations/2012/measurements/m-1/files/").mock(
        return_value=httpx.Response(201, json={
            "uuid": "f-1", "name": "spec.csv", "kind": "spectrum",
            "file_url": "https://cdn/x", "created_at": "2026-04-08T10:00:00Z"})
    )
    f = client.for_installation(2012).measurements.add_file("m-1", file=b"col\n1\n", filename="spec.csv")
    assert f.uuid == "f-1" and f.kind == "spectrum"


@respx.mock
def test_iter_for_point_cursor(client):
    route = respx.get(f"{BASE}/api/installations/2012/measurement-points/42/measurements/")
    route.side_effect = [
        httpx.Response(200, json={"items": [
            {"uuid": "m-1", "measurement_point_id": 42, "point_sequence": 1,
             "data": {}, "status": "good", "notes": "", "created_at": "t1"}],
            "next_cursor": "CUR2"}),
        httpx.Response(200, json={"items": [
            {"uuid": "m-2", "measurement_point_id": 42, "point_sequence": 2,
             "data": {}, "status": "good", "notes": "", "created_at": "t2"}],
            "next_cursor": None}),
    ]
    got = list(client.for_installation(2012).measurements.iter_for_point(42, page_size=1))
    assert [m.uuid for m in got] == ["m-1", "m-2"]
```

- [ ] **Step 2: Run — expect failure**

Run: `cd python && .venv/bin/pytest tests/test_registry.py::test_create_batch -q`
Expected: FAIL — `AttributeError: 'Measurements' object has no attribute 'create_batch'`.

- [ ] **Step 3: Extend `measurements.py`** — add imports and methods. Change the import line to:
```python
from ..models import BatchResult, FileAttachment, Measurement
```
Add these methods to the `Measurements` class:
```python
    def create_batch(self, items: list[dict]) -> BatchResult:
        body = self._http.request(
            "POST", self._path("/measurements/batch/"), json={"items": list(items)}
        )
        return BatchResult.from_dict(body)

    def add_file(
        self,
        measurement_uuid: str,
        *,
        file: str | Path | BinaryIO | bytes,
        filename: str = "attachment",
    ) -> FileAttachment:
        fh = file
        opened = False
        if isinstance(file, (str, Path)):
            filename = Path(file).name
            fh = open(file, "rb")  # noqa: SIM115
            opened = True
        elif isinstance(file, (bytes, bytearray)):
            import io
            fh = io.BytesIO(file)
        try:
            body = self._http.request(
                "POST",
                self._path(f"/measurements/{measurement_uuid}/files/"),
                files={"file": (filename, fh)},
            )
        finally:
            if opened:
                fh.close()
        return FileAttachment.from_dict(body)

    def iter_for_point(
        self,
        point_id: int,
        *,
        created_from: str | None = None,
        created_to: str | None = None,
        page_size: int = 100,
    ):
        """Yield every measurement for a point, following cursor pages."""
        cursor: str | None = ""
        path = self._path(f"/measurement-points/{point_id}/measurements/")
        while True:
            params = {
                "limit": page_size,
                "cursor": cursor,
                "created_from": created_from,
                "created_to": created_to,
            }
            params = {k: v for k, v in params.items() if v is not None}
            body = self._http.request("GET", path, params=params)
            for item in body["items"]:
                yield Measurement.from_dict(item)
            cursor = body.get("next_cursor")
            if not cursor:
                break
```
Also add the `created_from`/`created_to` filters to the existing `list_for_point`:
```python
    def list_for_point(self, point_id: int, *, limit: int = 50, offset: int = 0,
                       created_from: str | None = None, created_to: str | None = None) -> list[Measurement]:
        return _paginated(
            self._http,
            self._path(f"/measurement-points/{point_id}/measurements/"),
            params={"limit": limit, "offset": offset,
                    "created_from": created_from, "created_to": created_to},
            parse=Measurement.from_dict,
        )
```

- [ ] **Step 4: Run the new + full suite**

Run: `cd python && .venv/bin/pytest -q`
Expected: PASS (all of `test_client.py` + `test_registry.py`, including the `test_payload_too_large_error` and `test_add_file`).

- [ ] **Step 5: Commit**
```bash
git add python/
git commit -m "feat(py): batch measurements, file attach, cursor history iterator"
```

### Task 1.5: MaintNode client (Python)

**Files:**
- Create: `python/src/mechbase/maintnode.py`
- Modify: `python/src/mechbase/__init__.py`
- Test: `python/tests/test_maintnode.py` (new)

- [ ] **Step 1: Write failing tests** — create `python/tests/test_maintnode.py`:
```python
from __future__ import annotations

import httpx
import respx

from mechbase import MaintNode

BASE = "https://example.test"


@respx.mock
def test_config_and_no_auth_header():
    captured = {}

    def _cfg(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json="ssh-key: abc\nfoo: bar\n")

    respx.get(f"{BASE}/api/maintnode/node-1/config/").mock(side_effect=_cfg)
    node = MaintNode(node_uuid="node-1", base_url=BASE)
    cfg = node.config()
    assert cfg.startswith("ssh-key")
    assert captured["auth"] is None  # no bearer token sent


@respx.mock
def test_push_measurements():
    respx.post(f"{BASE}/api/maintnode/node-1/measurements/").mock(
        return_value=httpx.Response(200, json=[
            {"mapping_uuid": "map-1", "ok": True, "measurement_uuid": "m-1",
             "local_uuid": "L1", "error": ""}])
    )
    node = MaintNode(node_uuid="node-1", base_url=BASE)
    res = node.push_measurements([{"mapping_uuid": "map-1", "data": {"rms": 1.0}}])
    assert res[0].ok is True and res[0].measurement_uuid == "m-1"


@respx.mock
def test_heartbeat():
    respx.post(f"{BASE}/api/maintnode/node-1/heartbeat/").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    node = MaintNode(node_uuid="node-1", base_url=BASE)
    out = node.heartbeat(balena_uuid="bal-1", services={"agent": "1.2.3"})
    assert out["ok"] is True
```

- [ ] **Step 2: Run — expect failure**

Run: `cd python && .venv/bin/pytest tests/test_maintnode.py -q`
Expected: FAIL — `ImportError: cannot import name 'MaintNode'`.

- [ ] **Step 3: Create `python/src/mechbase/maintnode.py`**:
```python
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, BinaryIO

from ._http import HttpClient
from .models import MeasurementResult


class MaintNode:
    """Device-facing client for the maintnode integration API.

    Unauthenticated; the node is identified by ``node_uuid`` in the path.

    Usage::

        node = MaintNode(node_uuid="...")  # defaults to https://app.mechbase.io
        cfg = node.config()
        node.push_measurements([{"mapping_uuid": "...", "data": {"rms": 2.3}}])
    """

    DEFAULT_BASE_URL = "https://app.mechbase.io"

    def __init__(self, *, node_uuid: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self._http = HttpClient(token=None, base_url=base_url, timeout=timeout)
        self.node_uuid = node_uuid

    def _path(self, suffix: str) -> str:
        return f"/api/maintnode/{self.node_uuid}{suffix}"

    def config(self) -> str:
        return self._http.request("GET", self._path("/config/"))

    def heartbeat(self, *, balena_uuid: str = "", services: dict | None = None) -> dict:
        return self._http.request(
            "POST", self._path("/heartbeat/"),
            json={"balena_uuid": balena_uuid, "services": services or {}},
        )

    def push_measurements(self, items: list[dict]) -> list[MeasurementResult]:
        body = self._http.request(
            "POST", self._path("/measurements/"), json={"measurements": list(items)}
        )
        return [MeasurementResult.from_dict(r) for r in body]

    def add_measurement_file(
        self, measurement_uuid: str, *,
        file: str | Path | BinaryIO | bytes, filename: str = "attachment",
    ) -> dict:
        fh: Any = file
        opened = False
        if isinstance(file, (str, Path)):
            filename = Path(file).name
            fh = open(file, "rb")  # noqa: SIM115
            opened = True
        elif isinstance(file, (bytes, bytearray)):
            fh = io.BytesIO(file)
        try:
            return self._http.request(
                "POST", self._path(f"/measurements/{measurement_uuid}/file/"),
                files={"file": (filename, fh)},
            )
        finally:
            if opened:
                fh.close()

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
```

- [ ] **Step 4: Export `MaintNode`** — in `python/src/mechbase/__init__.py` add `from .maintnode import MaintNode` and add `"MaintNode"` to `__all__`.

- [ ] **Step 5: Run**

Run: `cd python && .venv/bin/pytest tests/test_maintnode.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**
```bash
git add python/
git commit -m "feat(py): maintnode device client"
```

### Task 1.6: Python version bump + example

**Files:**
- Modify: `python/pyproject.toml`
- Create: `python/examples/sync_registry.py`

- [ ] **Step 1: Bump version** — in `python/pyproject.toml` set `version = "0.2.0"`.

- [ ] **Step 2: Add a registry-sync example** — create `python/examples/sync_registry.py`:
```python
"""Upsert a section/zone/asset/point chain by external_id, then batch-push readings."""
from mechbase import Mechbase

client = Mechbase(token="...")
inst = client.for_installation(client.me().current_installation_id)

inst.sections.upsert(external_id="HALL-A", name="Hall A")
inst.zones.upsert(external_id="Z-1", name="Pump Row", section_external_id="HALL-A")
inst.assets.upsert(external_id="PUMP-1", name="Feed Pump 1", zone_external_id="Z-1",
                   equipment_type="pump", machine_class="II")
inst.measurement_points.upsert(external_id="PUMP-1-DE", name="Drive End",
                               asset_external_id="PUMP-1", transducer_type="accel",
                               measurement_unit_code="mm_s")

result = inst.measurements.create_batch([
    {"measurement_point_external_id": "PUMP-1-DE", "data": {"rms": 2.3}, "external_id": "r-1"},
])
print(f"created={result.created} duplicates={result.duplicates} errors={result.errors}")
```

- [ ] **Step 3: Run full Python suite + byte-compile the example**

Run: `cd python && .venv/bin/pytest -q && .venv/bin/python -m py_compile examples/sync_registry.py`
Expected: PASS, no compile error.

- [ ] **Step 4: Commit**
```bash
git add python/
git commit -m "chore(py): bump to 0.2.0 + registry-sync example"
```

---

## Phase 2 — Go

Work dir: `go/`. Run tests with `cd go && go test ./...`.

### Task 2.1: Go models, errors, version, and tokenless requests

**Files:**
- Modify: `go/pkg/mechbase/models.go`
- Modify: `go/pkg/mechbase/errors.go`
- Modify: `go/pkg/mechbase/client.go`

- [ ] **Step 1: Extend/add models** — in `models.go`, update `Asset`, `MeasurementPoint`, `Measurement` and append new types:
```go
// Asset is a tracked machine.
type Asset struct {
	UUID          string `json:"uuid"`
	AssetID       *int   `json:"asset_id"`
	Name          string `json:"name"`
	SectionID     *int   `json:"section_id"`
	ZoneID        *int   `json:"zone_id"`
	MachineClass  string `json:"machine_class"`
	EquipmentType string `json:"equipment_type"`
	Status        int    `json:"status"`
	ExternalID    *string `json:"external_id"`
}
```
Add `ExternalID *string \`json:"external_id"\`` to `MeasurementPoint` and `Measurement`. Append:
```go
// Section is a registry section.
type Section struct {
	UUID       string  `json:"uuid"`
	SectionID  *int    `json:"section_id"`
	Name       string  `json:"name"`
	ExternalID *string `json:"external_id"`
}

// Zone is a registry zone within a section.
type Zone struct {
	UUID       string  `json:"uuid"`
	ZoneID     *int    `json:"zone_id"`
	Name       string  `json:"name"`
	SectionID  *int    `json:"section_id"`
	ExternalID *string `json:"external_id"`
}

// DeleteResult is returned by DELETE endpoints.
type DeleteResult struct {
	Deleted bool   `json:"deleted"`
	UUID    string `json:"uuid"`
}

// BatchItemResult is the per-item outcome of a measurement batch.
type BatchItemResult struct {
	Index              int     `json:"index"`
	Status             string  `json:"status"`
	MeasurementPointID *int    `json:"measurement_point_id"`
	PointSequence      *int    `json:"point_sequence"`
	UUID               *string `json:"uuid"`
	ExternalID         *string `json:"external_id"`
	Detail             *string `json:"detail"`
}

// BatchResult is the response from a measurement batch push.
type BatchResult struct {
	Created    int               `json:"created"`
	Duplicates int               `json:"duplicates"`
	Errors     int               `json:"errors"`
	Results    []BatchItemResult `json:"results"`
}

// FileAttachment is a file attached to a measurement.
type FileAttachment struct {
	UUID      string `json:"uuid"`
	Name      string `json:"name"`
	Kind      string `json:"kind"`
	FileURL   string `json:"file_url"`
	CreatedAt string `json:"created_at"`
}

// MeasurementResult is the per-item outcome of a maintnode measurement push.
type MeasurementResult struct {
	MappingUUID     string  `json:"mapping_uuid"`
	OK              bool    `json:"ok"`
	MeasurementUUID *string `json:"measurement_uuid"`
	LocalUUID       string  `json:"local_uuid"`
	Error           string  `json:"error"`
}

// cursorEnvelope is the cursor-paginated wrapper for history iteration.
type cursorEnvelope[T any] struct {
	Items      []T     `json:"items"`
	NextCursor *string `json:"next_cursor"`
}
```

- [ ] **Step 2: Add error sentinels + mapping** — in `errors.go` add to the `var (...)` block:
```go
	ErrConflict   = errors.New("mechbase: conflict")
	ErrTooLarge   = errors.New("mechbase: payload too large")
```
and in `Unwrap()` add cases:
```go
	case 409:
		return ErrConflict
	case 413:
		return ErrTooLarge
```

- [ ] **Step 3: Version bump + tokenless request** — in `client.go` set `const userAgent = "mechbase-go/0.2"`. In `newRequest`, make the auth header conditional:
```go
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
```

- [ ] **Step 4: Update the User-Agent assertion** — in `client_test.go`, `assertAuth` expects `"mechbase-go/0.2"`.

- [ ] **Step 5: Build (tests come with each feature task)**

Run: `cd go && go build ./... && go vet ./...`
Expected: no errors.

- [ ] **Step 6: Commit**
```bash
git add go/
git commit -m "feat(go): models, conflict/too-large errors, tokenless requests, v0.2"
```

### Task 2.2: Go registry CRUD

**Files:**
- Modify: `go/pkg/mechbase/assets.go`
- Modify: `go/pkg/mechbase/measurement_points.go`
- Create: `go/pkg/mechbase/sections.go`
- Create: `go/pkg/mechbase/zones.go`
- Modify: `go/pkg/mechbase/client.go` (wire new resources into `Installation_`)
- Test: `go/pkg/mechbase/registry_test.go` (new)

- [ ] **Step 1: Write a failing test** — create `go/pkg/mechbase/registry_test.go`:
```go
package mechbase

import (
	"context"
	"errors"
	"net/http"
	"testing"
)

func TestAssetCRUD(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == "POST" && r.URL.Path == "/api/installations/2012/assets":
			w.WriteHeader(201)
			_, _ = w.Write([]byte(`{"uuid":"a-1","asset_id":7,"name":"Pump 7","section_id":3,"zone_id":2,"machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}`))
		case r.Method == "PATCH" && r.URL.Path == "/api/installations/2012/assets/7":
			_, _ = w.Write([]byte(`{"uuid":"a-1","asset_id":7,"name":"Pump 7c","section_id":3,"zone_id":2,"machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}`))
		case r.Method == "DELETE" && r.URL.Path == "/api/installations/2012/assets/7":
			if r.URL.Query().Get("cascade") != "true" {
				t.Fatalf("cascade=%s", r.URL.Query().Get("cascade"))
			}
			_, _ = w.Write([]byte(`{"deleted":true,"uuid":"a-1"}`))
		default:
			t.Fatalf("unexpected %s %s", r.Method, r.URL.Path)
		}
	})
	defer stop()

	assets := c.ForInstallation(2012).Assets
	created, err := assets.Create(context.Background(), AssetInput{Name: ptr("Pump 7"), ExternalID: ptr("P-7")})
	if err != nil || created.EquipmentType != "pump" {
		t.Fatalf("create: %+v %v", created, err)
	}
	updated, err := assets.Update(context.Background(), 7, AssetInput{Name: ptr("Pump 7c")})
	if err != nil || updated.Name != "Pump 7c" {
		t.Fatalf("update: %+v %v", updated, err)
	}
	del, err := assets.Delete(context.Background(), 7, true)
	if err != nil || !del.Deleted {
		t.Fatalf("delete: %+v %v", del, err)
	}
}

func TestConflictIsErrConflict(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(409)
		_, _ = w.Write([]byte(`{"detail":"dup"}`))
	})
	defer stop()
	_, err := c.ForInstallation(2012).Assets.Create(context.Background(), AssetInput{ExternalID: ptr("P-7")})
	if !errors.Is(err, ErrConflict) {
		t.Fatalf("want ErrConflict, got %v", err)
	}
}

func ptr[T any](v T) *T { return &v }
```

- [ ] **Step 2: Run — expect failure**

Run: `cd go && go test ./... -run TestAssetCRUD`
Expected: FAIL — `AssetInput` / `Create` undefined.

- [ ] **Step 3: Add asset write methods + input** — append to `assets.go`:
```go
// AssetInput is the create/upsert/update body. Nil fields are omitted.
type AssetInput struct {
	Name              *string `json:"name,omitempty"`
	ExternalID        *string `json:"external_id,omitempty"`
	SectionID         *int    `json:"section_id,omitempty"`
	SectionExternalID *string `json:"section_external_id,omitempty"`
	ZoneID            *int    `json:"zone_id,omitempty"`
	ZoneExternalID    *string `json:"zone_external_id,omitempty"`
	EquipmentType     *string `json:"equipment_type,omitempty"`
	MachineClass      *string `json:"machine_class,omitempty"`
}

// Create creates an asset.
func (a *Assets) Create(ctx context.Context, in AssetInput) (*Asset, error) {
	var out Asset
	if err := a.client.doJSON(ctx, http.MethodPost, pathf(a.iid, "/assets"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Upsert creates or updates an asset, matched by external_id.
func (a *Assets) Upsert(ctx context.Context, in AssetInput) (*Asset, error) {
	var out Asset
	if err := a.client.doJSON(ctx, http.MethodPut, pathf(a.iid, "/assets"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Update partially updates an asset by numeric id.
func (a *Assets) Update(ctx context.Context, assetID int, in AssetInput) (*Asset, error) {
	var out Asset
	if err := a.client.doJSON(ctx, http.MethodPatch, pathf(a.iid, fmt.Sprintf("/assets/%d", assetID)), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Delete removes an asset; cascade also removes children.
func (a *Assets) Delete(ctx context.Context, assetID int, cascade bool) (*DeleteResult, error) {
	q := url.Values{}
	if cascade {
		q.Set("cascade", "true")
	}
	var out DeleteResult
	if err := a.client.doJSON(ctx, http.MethodDelete, pathf(a.iid, fmt.Sprintf("/assets/%d", assetID)), q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
```

- [ ] **Step 4: Add point write methods + input** — append to `measurement_points.go` the analogous block. `PointInput`:
```go
// PointInput is the create/upsert/update body for measurement points.
type PointInput struct {
	Name                *string `json:"name,omitempty"`
	ExternalID          *string `json:"external_id,omitempty"`
	AssetID             *int    `json:"asset_id,omitempty"`
	AssetExternalID     *string `json:"asset_external_id,omitempty"`
	TransducerType      *string `json:"transducer_type,omitempty"`
	MeasurementUnitCode *string `json:"measurement_unit_code,omitempty"`
	Location            *string `json:"location,omitempty"`
	BodySegment         *int    `json:"body_segment,omitempty"`
	BodyAngle           *int    `json:"body_angle,omitempty"`
	MachineClass        *string `json:"machine_class,omitempty"`
}
```
Then `Create`/`Upsert`/`Update`/`Delete` methods on `*MeasurementPoints`, identical to the asset block but: receiver `m *MeasurementPoints`, return `*MeasurementPoint`, collection path `"/measurement-points"`, item path `fmt.Sprintf("/measurement-points/%d", pointID)`, param name `pointID int`.

- [ ] **Step 5: Create `sections.go`**:
```go
package mechbase

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
)

// Sections is the section registry resource.
type Sections struct {
	client *Client
	iid    int
}

// SectionInput is the create/upsert/update body for sections.
type SectionInput struct {
	Name       *string `json:"name,omitempty"`
	ExternalID *string `json:"external_id,omitempty"`
}

// ListSectionsOptions filters Sections.List. Zero values are omitted.
type ListSectionsOptions struct {
	Q      string
	Limit  int
	Offset int
}

func (s *Sections) List(ctx context.Context, opts ListSectionsOptions) ([]Section, error) {
	q := url.Values{}
	if opts.Q != "" {
		q.Set("q", opts.Q)
	}
	addPaging(q, opts.Limit, opts.Offset)
	var env listEnvelope[Section]
	if err := s.client.doJSON(ctx, http.MethodGet, pathf(s.iid, "/sections"), q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}

func (s *Sections) Get(ctx context.Context, sectionID int) (*Section, error) {
	var out Section
	if err := s.client.doJSON(ctx, http.MethodGet, pathf(s.iid, fmt.Sprintf("/sections/%d", sectionID)), nil, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (s *Sections) Create(ctx context.Context, in SectionInput) (*Section, error) {
	var out Section
	if err := s.client.doJSON(ctx, http.MethodPost, pathf(s.iid, "/sections"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (s *Sections) Upsert(ctx context.Context, in SectionInput) (*Section, error) {
	var out Section
	if err := s.client.doJSON(ctx, http.MethodPut, pathf(s.iid, "/sections"), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (s *Sections) Update(ctx context.Context, sectionID int, in SectionInput) (*Section, error) {
	var out Section
	if err := s.client.doJSON(ctx, http.MethodPatch, pathf(s.iid, fmt.Sprintf("/sections/%d", sectionID)), nil, in, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (s *Sections) Delete(ctx context.Context, sectionID int, cascade bool) (*DeleteResult, error) {
	q := url.Values{}
	if cascade {
		q.Set("cascade", "true")
	}
	var out DeleteResult
	if err := s.client.doJSON(ctx, http.MethodDelete, pathf(s.iid, fmt.Sprintf("/sections/%d", sectionID)), q, nil, &out); err != nil {
		return nil, err
	}
	return &out, nil
}
```

- [ ] **Step 6: Create `zones.go`** — same as `sections.go` but: type `Zones`, `ZoneInput{Name, ExternalID, SectionID *int, SectionExternalID *string}` (all `omitempty`), `ListZonesOptions{Q string; SectionID int; Limit; Offset}` (set `section_id` query when non-zero), return `*Zone`/`[]Zone`, paths `"/zones"` and `"/zones/%d"`, param `zoneID int`.

- [ ] **Step 7: Wire into `Installation_`** — in `client.go` add fields `Sections *Sections` and `Zones *Zones` to the struct and initialize them in `ForInstallation`:
```go
		Sections:          &Sections{client: c, iid: id},
		Zones:             &Zones{client: c, iid: id},
```

- [ ] **Step 8: Run**

Run: `cd go && go test ./... -run 'TestAssetCRUD|TestConflict'`
Expected: PASS.

- [ ] **Step 9: Commit**
```bash
git add go/
git commit -m "feat(go): registry CRUD for assets, points, sections, zones"
```

### Task 2.3: Go batch, file attach, cursor history

**Files:**
- Modify: `go/pkg/mechbase/measurements.go`
- Test: `go/pkg/mechbase/registry_test.go`

- [ ] **Step 1: Write failing tests** — append to `registry_test.go`:
```go
func TestCreateBatch(t *testing.T) {
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/installations/2012/measurements/batch/" {
			t.Fatalf("path %s", r.URL.Path)
		}
		_, _ = w.Write([]byte(`{"created":1,"duplicates":0,"errors":0,"results":[{"index":0,"status":"created","measurement_point_id":1,"point_sequence":5,"uuid":"m-1","external_id":"E-0","detail":null}]}`))
	})
	defer stop()
	res, err := c.ForInstallation(2012).Measurements.CreateBatch(context.Background(), []MeasurementInput{
		{MeasurementPointID: ptr(1), Data: map[string]any{"rms": 2.3}, ExternalID: ptr("E-0")},
	})
	if err != nil || res.Created != 1 || res.Results[0].Status != "created" {
		t.Fatalf("batch: %+v %v", res, err)
	}
}

func TestIterForPoint(t *testing.T) {
	page := 0
	c, stop := newTestServer(t, func(w http.ResponseWriter, r *http.Request) {
		page++
		if page == 1 {
			_, _ = w.Write([]byte(`{"items":[{"uuid":"m-1","measurement_point_id":42,"point_sequence":1,"data":{},"status":"good","notes":"","created_at":"t1"}],"next_cursor":"CUR2"}`))
		} else {
			_, _ = w.Write([]byte(`{"items":[{"uuid":"m-2","measurement_point_id":42,"point_sequence":2,"data":{},"status":"good","notes":"","created_at":"t2"}],"next_cursor":null}`))
		}
	})
	defer stop()
	var got []string
	err := c.ForInstallation(2012).Measurements.IterForPoint(context.Background(), 42, IterOptions{PageSize: 1}, func(m Measurement) error {
		got = append(got, m.UUID)
		return nil
	})
	if err != nil || len(got) != 2 || got[1] != "m-2" {
		t.Fatalf("iter: %v %v", got, err)
	}
}
```

- [ ] **Step 2: Run — expect failure**

Run: `cd go && go test ./... -run TestCreateBatch`
Expected: FAIL — `MeasurementInput`/`CreateBatch` undefined.

- [ ] **Step 3: Extend `measurements.go`** — append:
```go
// MeasurementInput is one item in a measurement batch. Supply exactly one of
// PointID / PointExternalID. Nil fields are omitted.
type MeasurementInput struct {
	MeasurementPointID         *int           `json:"measurement_point_id,omitempty"`
	MeasurementPointExternalID *string        `json:"measurement_point_external_id,omitempty"`
	Data                       map[string]any `json:"data"`
	Notes                      *string        `json:"notes,omitempty"`
	SessionID                  *string        `json:"session_id,omitempty"`
	Timestamp                  *string        `json:"timestamp,omitempty"`
	ExternalID                 *string        `json:"external_id,omitempty"`
}

// CreateBatch pushes many measurements in one request.
func (m *Measurements) CreateBatch(ctx context.Context, items []MeasurementInput) (*BatchResult, error) {
	body := map[string]any{"items": items}
	var out BatchResult
	if err := m.client.doJSON(ctx, http.MethodPost, pathf(m.iid, "/measurements/batch/"), nil, body, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// AddFile attaches a file to an existing measurement (multipart).
func (m *Measurements) AddFile(ctx context.Context, measurementUUID, filename string, file io.Reader) (*FileAttachment, error) {
	if filename == "" {
		filename = "attachment"
	}
	files := []filePart{{Field: "file", Filename: filename, Reader: file}}
	var out FileAttachment
	if err := m.client.doMultipart(ctx, pathf(m.iid, fmt.Sprintf("/measurements/%s/files/", measurementUUID)), nil, files, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// IterOptions configures IterForPoint.
type IterOptions struct {
	CreatedFrom string
	CreatedTo   string
	PageSize    int
}

// IterForPoint streams the full history for a point, following cursor pages.
// The callback is invoked per measurement; return an error to stop.
func (m *Measurements) IterForPoint(ctx context.Context, pointID int, opts IterOptions, fn func(Measurement) error) error {
	cursor := ""
	path := pathf(m.iid, fmt.Sprintf("/measurement-points/%d/measurements/", pointID))
	for {
		q := url.Values{}
		q.Set("cursor", cursor)
		if opts.PageSize > 0 {
			q.Set("limit", fmt.Sprintf("%d", opts.PageSize))
		}
		if opts.CreatedFrom != "" {
			q.Set("created_from", opts.CreatedFrom)
		}
		if opts.CreatedTo != "" {
			q.Set("created_to", opts.CreatedTo)
		}
		var env cursorEnvelope[Measurement]
		if err := m.client.doJSON(ctx, http.MethodGet, path, q, nil, &env); err != nil {
			return err
		}
		for _, item := range env.Items {
			if err := fn(item); err != nil {
				return err
			}
		}
		if env.NextCursor == nil || *env.NextCursor == "" {
			return nil
		}
		cursor = *env.NextCursor
	}
}
```
Also add the date filters to `ListForPoint` by changing its signature to accept an options struct, OR add a sibling. To stay backward-compatible, append optional filters via a new options-based method is overkill — instead add params to the existing one. Change `ListForPoint`:
```go
// ListForPointOptions filters ListForPoint. Zero values are omitted.
type ListForPointOptions struct {
	Limit       int
	Offset      int
	CreatedFrom string
	CreatedTo   string
}

// ListForPoint returns one offset page of a point's history.
func (m *Measurements) ListForPoint(ctx context.Context, pointID int, opts ListForPointOptions) ([]Measurement, error) {
	q := url.Values{}
	addPaging(q, opts.Limit, opts.Offset)
	if opts.CreatedFrom != "" {
		q.Set("created_from", opts.CreatedFrom)
	}
	if opts.CreatedTo != "" {
		q.Set("created_to", opts.CreatedTo)
	}
	var env listEnvelope[Measurement]
	path := pathf(m.iid, fmt.Sprintf("/measurement-points/%d/measurements/", pointID))
	if err := m.client.doJSON(ctx, http.MethodGet, path, q, nil, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}
```
> NOTE: this changes `ListForPoint`'s signature from `(ctx, pointID, limit, offset)` to `(ctx, pointID, opts)`. Grep for existing callers and update them (Step 4).

- [ ] **Step 4: Update existing `ListForPoint` callers** — run `grep -rn "ListForPoint" go/` and update any call (e.g. in `go/examples/`) to the new `ListForPointOptions{}` form.

- [ ] **Step 5: Run**

Run: `cd go && go test ./... -run 'TestCreateBatch|TestIterForPoint' && go build ./...`
Expected: PASS, build clean.

- [ ] **Step 6: Commit**
```bash
git add go/
git commit -m "feat(go): batch measurements, file attach, cursor history"
```

### Task 2.4: Go MaintNode client

**Files:**
- Create: `go/pkg/mechbase/maintnode.go`
- Test: `go/pkg/mechbase/maintnode_test.go` (new)

- [ ] **Step 1: Write failing test** — create `go/pkg/mechbase/maintnode_test.go`:
```go
package mechbase

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestMaintNodePush(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "" {
			t.Fatalf("unexpected auth header: %s", r.Header.Get("Authorization"))
		}
		switch r.URL.Path {
		case "/api/maintnode/node-1/config/":
			_, _ = w.Write([]byte(`"ssh: abc"`))
		case "/api/maintnode/node-1/measurements/":
			_, _ = w.Write([]byte(`[{"mapping_uuid":"map-1","ok":true,"measurement_uuid":"m-1","local_uuid":"L1","error":""}]`))
		default:
			t.Fatalf("unexpected %s", r.URL.Path)
		}
	}))
	defer srv.Close()

	node := NewMaintNode("node-1", srv.URL)
	cfg, err := node.Config(context.Background())
	if err != nil || cfg != "ssh: abc" {
		t.Fatalf("config: %q %v", cfg, err)
	}
	res, err := node.PushMeasurements(context.Background(), []MaintNodeMeasurementInput{
		{MappingUUID: "map-1", Data: map[string]any{"rms": 1.0}},
	})
	if err != nil || !res[0].OK {
		t.Fatalf("push: %+v %v", res, err)
	}
}
```

- [ ] **Step 2: Run — expect failure**

Run: `cd go && go test ./... -run TestMaintNodePush`
Expected: FAIL — `NewMaintNode` undefined.

- [ ] **Step 3: Create `go/pkg/mechbase/maintnode.go`**:
```go
package mechbase

import (
	"context"
	"fmt"
	"io"
	"net/http"
)

// MaintNode is the device-facing client for the maintnode integration API.
// It sends no Authorization header; the node is identified by nodeUUID.
type MaintNode struct {
	client   *Client
	nodeUUID string
}

// NewMaintNode creates a tokenless maintnode client. Empty baseURL uses DefaultBaseURL.
func NewMaintNode(nodeUUID, baseURL string, opts ...Option) *MaintNode {
	return &MaintNode{client: New("", baseURL, opts...), nodeUUID: nodeUUID}
}

// MaintNodeMeasurementInput is one item in a maintnode measurement push.
type MaintNodeMeasurementInput struct {
	MappingUUID string         `json:"mapping_uuid"`
	Data        map[string]any `json:"data"`
	Timestamp   *string        `json:"timestamp,omitempty"`
	LocalUUID   string         `json:"local_uuid,omitempty"`
}

func (n *MaintNode) path(suffix string) string {
	return fmt.Sprintf("/api/maintnode/%s%s", n.nodeUUID, suffix)
}

// Config returns the raw node config blob.
func (n *MaintNode) Config(ctx context.Context) (string, error) {
	var out string
	if err := n.client.doJSON(ctx, http.MethodGet, n.path("/config/"), nil, nil, &out); err != nil {
		return "", err
	}
	return out, nil
}

// Heartbeat reports node liveness and returns the server's ack object.
func (n *MaintNode) Heartbeat(ctx context.Context, balenaUUID string, services map[string]any) (map[string]any, error) {
	body := map[string]any{"balena_uuid": balenaUUID, "services": services}
	var out map[string]any
	if err := n.client.doJSON(ctx, http.MethodPost, n.path("/heartbeat/"), nil, body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// PushMeasurements submits measurements collected by the node.
func (n *MaintNode) PushMeasurements(ctx context.Context, items []MaintNodeMeasurementInput) ([]MeasurementResult, error) {
	body := map[string]any{"measurements": items}
	var out []MeasurementResult
	if err := n.client.doJSON(ctx, http.MethodPost, n.path("/measurements/"), nil, body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// AddMeasurementFile attaches a file to a node measurement (multipart).
func (n *MaintNode) AddMeasurementFile(ctx context.Context, measurementUUID, filename string, file io.Reader) (map[string]any, error) {
	if filename == "" {
		filename = "attachment"
	}
	files := []filePart{{Field: "file", Filename: filename, Reader: file}}
	var out map[string]any
	if err := n.client.doMultipart(ctx, n.path(fmt.Sprintf("/measurements/%s/file/", measurementUUID)), nil, files, &out); err != nil {
		return nil, err
	}
	return out, nil
}
```

- [ ] **Step 4: Run + full suite**

Run: `cd go && go test ./...`
Expected: PASS (all Go tests).

- [ ] **Step 5: Commit**
```bash
git add go/
git commit -m "feat(go): maintnode device client"
```

---

## Phase 3 — Swift

Work dir: `swift/`. Run tests with `cd swift && swift test`.

### Task 3.1: Swift models + errors + version

**Files:**
- Modify: `swift/Sources/Mechbase/Models.swift`
- Modify: `swift/Sources/Mechbase/Errors.swift`
- Modify: `swift/Sources/Mechbase/HTTPClient.swift`

- [ ] **Step 1: Extend `Asset`** in `Models.swift` — add `sectionId: Int?`, `equipmentType: String`, `externalId: String?` with coding keys `section_id`, `equipment_type`, `external_id`, decoding `sectionId`/`externalId` via `decodeIfPresent`, `equipmentType` via `(try? c.decode(...)) ?? ""`.

- [ ] **Step 2: Add `externalId: String?`** to `MeasurementPoint` (it has the default member-wise decoder; add `case externalId = "external_id"` and the property — since `MeasurementPoint` uses synthesized `Codable`, just add the optional property + coding key) and to `Measurement` (add property + `case externalId = "external_id"` + `self.externalId = try c.decodeIfPresent(String.self, forKey: .externalId)` in its custom init).

- [ ] **Step 3: Append new structs** to `Models.swift`:
```swift
public struct Section: Codable, Sendable {
    public let uuid: String
    public let sectionId: Int?
    public let name: String
    public let externalId: String?
    enum CodingKeys: String, CodingKey {
        case uuid, name
        case sectionId = "section_id"
        case externalId = "external_id"
    }
}

public struct Zone: Codable, Sendable {
    public let uuid: String
    public let zoneId: Int?
    public let name: String
    public let sectionId: Int?
    public let externalId: String?
    enum CodingKeys: String, CodingKey {
        case uuid, name
        case zoneId = "zone_id"
        case sectionId = "section_id"
        case externalId = "external_id"
    }
}

public struct DeleteResult: Codable, Sendable {
    public let deleted: Bool
    public let uuid: String
}

public struct BatchItemResult: Codable, Sendable {
    public let index: Int
    public let status: String
    public let measurementPointId: Int?
    public let pointSequence: Int?
    public let uuid: String?
    public let externalId: String?
    public let detail: String?
    enum CodingKeys: String, CodingKey {
        case index, status, uuid, detail
        case measurementPointId = "measurement_point_id"
        case pointSequence = "point_sequence"
        case externalId = "external_id"
    }
}

public struct BatchResult: Codable, Sendable {
    public let created: Int
    public let duplicates: Int
    public let errors: Int
    public let results: [BatchItemResult]
}

public struct FileAttachment: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let kind: String
    public let fileUrl: String
    public let createdAt: String
    enum CodingKeys: String, CodingKey {
        case uuid, name, kind
        case fileUrl = "file_url"
        case createdAt = "created_at"
    }
}

/// Cursor-paginated wrapper for history iteration.
struct CursorPage<T: Decodable>: Decodable {
    let items: [T]
    let nextCursor: String?
    enum CodingKeys: String, CodingKey {
        case items
        case nextCursor = "next_cursor"
    }
}
```

- [ ] **Step 4: Add error cases + mapping + version** — in `Errors.swift` add cases:
```swift
    /// 409.
    case conflict(String)
    /// 413.
    case tooLarge(String)
```
and in `description` add `case .conflict(let m): return "conflict: \(m)"` and `case .tooLarge(let m): return "tooLarge: \(m)"`. In `HTTPClient.swift` `send`, add to the `switch status`:
```swift
        case 409: throw MechbaseError.conflict(message)
        case 413: throw MechbaseError.tooLarge(message)
```
and bump the User-Agent to `"mechbase-swift/0.2"`.

- [ ] **Step 5: Build**

Run: `cd swift && swift build`
Expected: builds (resources come next; no test yet).

- [ ] **Step 6: Commit**
```bash
git add swift/
git commit -m "feat(swift): models, conflict/tooLarge errors, v0.2"
```

### Task 3.2: Swift registry CRUD

**Files:**
- Modify: `swift/Sources/Mechbase/HTTPClient.swift` (add put/patch/delete verbs)
- Modify: `swift/Sources/Mechbase/Assets.swift`
- Modify: `swift/Sources/Mechbase/MeasurementPoints.swift`
- Create: `swift/Sources/Mechbase/Sections.swift`
- Create: `swift/Sources/Mechbase/Zones.swift`
- Modify: `swift/Sources/Mechbase/Installation.swift`
- Test: `swift/Tests/MechbaseTests/RegistryTests.swift` (new)

- [ ] **Step 1: Write a failing test** — create `swift/Tests/MechbaseTests/RegistryTests.swift`:
```swift
import XCTest
@testable import Mechbase

@MainActor
final class RegistryTests: XCTestCase {
    var client: MechbaseClient!

    override func setUp() {
        super.setUp()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        client = MechbaseClient(token: "tok", baseURL: URL(string: "https://example.test")!,
                                session: URLSession(configuration: config))
    }
    override func tearDown() { MockURLProtocol.handler = nil; client = nil; super.tearDown() }
    private func json(_ s: String) -> Data { s.data(using: .utf8)! }

    func testCreateAsset() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/installations/2012/assets")
            XCTAssertEqual(req.httpMethod, "POST")
            return (201, self.json("""
            {"uuid":"a-1","asset_id":7,"name":"Pump 7","section_id":3,"zone_id":2,
             "machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}
            """))
        }
        let a = try await client.forInstallation(id: 2012).assets.create(
            AssetInput(name: "Pump 7", externalId: "P-7"))
        XCTAssertEqual(a.assetId, 7)
        XCTAssertEqual(a.equipmentType, "pump")
    }

    func testCreateZone() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/installations/2012/zones")
            return (201, self.json("""
            {"uuid":"z-1","zone_id":9,"name":"Zone 9","section_id":3,"external_id":"Z-9"}
            """))
        }
        let z = try await client.forInstallation(id: 2012).zones.create(
            ZoneInput(name: "Zone 9", externalId: "Z-9", sectionExternalId: "S-1"))
        XCTAssertEqual(z.zoneId, 9)
    }
}
```

- [ ] **Step 2: Run — expect failure**

Run: `cd swift && swift test --filter RegistryTests`
Expected: FAIL — `AssetInput`/`create` not found.

- [ ] **Step 3: Add verbs to `HTTPClient.swift`** — alongside `postJSON`, add:
```swift
    func putJSON<T: Decodable, B: Encodable>(_ path: String, body: B, as: T.Type) async throws -> T {
        var req = makeRequest("PUT", url(path: path))
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(body)
        return try await send(req)
    }

    func patchJSON<T: Decodable, B: Encodable>(_ path: String, body: B, as: T.Type) async throws -> T {
        var req = makeRequest("PATCH", url(path: path))
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(body)
        return try await send(req)
    }

    func delete<T: Decodable>(_ path: String, query: [URLQueryItem] = [], as: T.Type) async throws -> T {
        let req = makeRequest("DELETE", url(path: path, query: query))
        return try await send(req)
    }
```

- [ ] **Step 4: Rewrite `Assets.swift`** to add the input + write methods:
```swift
import Foundation

/// Create/upsert/update body for assets. Nil fields are omitted by the encoder
/// (the SDK JSONEncoder skips nil optionals).
public struct AssetInput: Encodable, Sendable {
    public var name: String?
    public var externalId: String?
    public var sectionId: Int?
    public var sectionExternalId: String?
    public var zoneId: Int?
    public var zoneExternalId: String?
    public var equipmentType: String?
    public var machineClass: String?

    public init(name: String? = nil, externalId: String? = nil, sectionId: Int? = nil,
                sectionExternalId: String? = nil, zoneId: Int? = nil, zoneExternalId: String? = nil,
                equipmentType: String? = nil, machineClass: String? = nil) {
        self.name = name; self.externalId = externalId; self.sectionId = sectionId
        self.sectionExternalId = sectionExternalId; self.zoneId = zoneId
        self.zoneExternalId = zoneExternalId; self.equipmentType = equipmentType
        self.machineClass = machineClass
    }

    enum CodingKeys: String, CodingKey {
        case name
        case externalId = "external_id"
        case sectionId = "section_id"
        case sectionExternalId = "section_external_id"
        case zoneId = "zone_id"
        case zoneExternalId = "zone_external_id"
        case equipmentType = "equipment_type"
        case machineClass = "machine_class"
    }
}

public struct Assets: Sendable {
    let scope: InstallationScope
    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    public func list(query: String? = nil, zoneId: Int? = nil, limit: Int = 50, offset: Int = 0) async throws -> [Asset] {
        let q: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "zone_id", value: zoneId.map(String.init)),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        return try await scope.http.get(scope.path("/assets"), query: q, as: Page<Asset>.self).items
    }

    public func get(id: Int) async throws -> Asset {
        try await scope.http.get(scope.path("/assets/\(id)"), as: Asset.self)
    }

    public func create(_ input: AssetInput) async throws -> Asset {
        try await scope.http.postJSON(scope.path("/assets"), body: input, as: Asset.self)
    }

    public func upsert(_ input: AssetInput) async throws -> Asset {
        try await scope.http.putJSON(scope.path("/assets"), body: input, as: Asset.self)
    }

    public func update(id: Int, _ input: AssetInput) async throws -> Asset {
        try await scope.http.patchJSON(scope.path("/assets/\(id)"), body: input, as: Asset.self)
    }

    public func delete(id: Int, cascade: Bool = false) async throws -> DeleteResult {
        let q = cascade ? [URLQueryItem(name: "cascade", value: "true")] : []
        return try await scope.http.delete(scope.path("/assets/\(id)"), query: q, as: DeleteResult.self)
    }
}
```
> NOTE: the existing `HTTPClient` uses a `JSONEncoder` whose default skips `nil` optionals, so omitted fields stay out of the PATCH body. Confirm by asserting a request body in a later test if desired.

- [ ] **Step 5: Rewrite `MeasurementPoints.swift`** analogously — add `PointInput` (fields per Shared Reference, coding keys snake_case) and `create/upsert/update/delete` using `/measurement-points` and `/measurement-points/\(id)`. Keep the existing `list`/`get`.

- [ ] **Step 6: Create `Sections.swift`** and **`Zones.swift`** mirroring `Assets.swift` with their input/paths:
  - `SectionInput{name, externalId}` keys `name`,`external_id`; paths `/sections`, `/sections/\(id)`; returns `Section`; list has `q/limit/offset`.
  - `ZoneInput{name, externalId, sectionId, sectionExternalId}`; paths `/zones`, `/zones/\(id)`; returns `Zone`; list has `q/sectionId/limit/offset`.

- [ ] **Step 7: Wire into `Installation.swift`** — add `public let sections: Sections` and `public let zones: Zones` properties and initialize them in `init`.

- [ ] **Step 8: Run**

Run: `cd swift && swift test --filter RegistryTests`
Expected: PASS.

- [ ] **Step 9: Commit**
```bash
git add swift/
git commit -m "feat(swift): registry CRUD for assets, points, sections, zones"
```

### Task 3.3: Swift batch, file attach, cursor history

**Files:**
- Modify: `swift/Sources/Mechbase/Measurements.swift`
- Test: `swift/Tests/MechbaseTests/RegistryTests.swift`

- [ ] **Step 1: Write failing tests** — append to `RegistryTests.swift`:
```swift
    func testCreateBatch() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/installations/2012/measurements/batch/")
            return (200, self.json("""
            {"created":1,"duplicates":0,"errors":0,"results":[
              {"index":0,"status":"created","measurement_point_id":1,"point_sequence":5,
               "uuid":"m-1","external_id":"E-0","detail":null}]}
            """))
        }
        let res = try await client.forInstallation(id: 2012).measurements.createBatch([
            MeasurementInput(measurementPointId: 1, data: ["rms": 2.3], externalId: "E-0"),
        ])
        XCTAssertEqual(res.created, 1)
        XCTAssertEqual(res.results.first?.status, "created")
    }

    func testIterForPoint() async throws {
        var page = 0
        MockURLProtocol.handler = { _ in
            page += 1
            if page == 1 {
                return (200, self.json("""
                {"items":[{"uuid":"m-1","measurement_point_id":42,"point_sequence":1,
                 "data":{},"status":"good","notes":"","created_at":"t1"}],"next_cursor":"CUR2"}
                """))
            }
            return (200, self.json("""
            {"items":[{"uuid":"m-2","measurement_point_id":42,"point_sequence":2,
             "data":{},"status":"good","notes":"","created_at":"t2"}],"next_cursor":null}
            """))
        }
        var got: [String] = []
        for try await m in client.forInstallation(id: 2012).measurements.iterForPoint(pointId: 42, pageSize: 1) {
            got.append(m.uuid)
        }
        XCTAssertEqual(got, ["m-1", "m-2"])
    }
```

- [ ] **Step 2: Run — expect failure**

Run: `cd swift && swift test --filter RegistryTests/testCreateBatch`
Expected: FAIL — `MeasurementInput`/`createBatch` not found.

- [ ] **Step 3: Extend `Measurements.swift`** — append:
```swift
/// One item in a measurement batch. Supply exactly one of pointId / pointExternalId.
public struct MeasurementInput: Encodable, Sendable {
    public var measurementPointId: Int?
    public var measurementPointExternalId: String?
    public var data: JSONValue
    public var notes: String?
    public var sessionId: String?
    public var timestamp: String?
    public var externalId: String?

    public init(measurementPointId: Int? = nil, measurementPointExternalId: String? = nil,
                data: JSONValue, notes: String? = nil, sessionId: String? = nil,
                timestamp: String? = nil, externalId: String? = nil) {
        self.measurementPointId = measurementPointId
        self.measurementPointExternalId = measurementPointExternalId
        self.data = data; self.notes = notes; self.sessionId = sessionId
        self.timestamp = timestamp; self.externalId = externalId
    }

    public init(measurementPointId: Int? = nil, measurementPointExternalId: String? = nil,
                data: [String: Any], notes: String? = nil, sessionId: String? = nil,
                timestamp: String? = nil, externalId: String? = nil) {
        self.init(measurementPointId: measurementPointId,
                  measurementPointExternalId: measurementPointExternalId,
                  data: JSONValue.from(data), notes: notes, sessionId: sessionId,
                  timestamp: timestamp, externalId: externalId)
    }

    enum CodingKeys: String, CodingKey {
        case data, notes, timestamp
        case measurementPointId = "measurement_point_id"
        case measurementPointExternalId = "measurement_point_external_id"
        case sessionId = "session_id"
        case externalId = "external_id"
    }
}

public extension Measurements {
    private struct BatchBody: Encodable { let items: [MeasurementInput] }

    /// Push many measurements in one request.
    func createBatch(_ items: [MeasurementInput]) async throws -> BatchResult {
        try await scope.http.postJSON(scope.path("/measurements/batch/"),
                                      body: BatchBody(items: items), as: BatchResult.self)
    }

    /// Attach a file to an existing measurement (multipart).
    func addFile(measurementUUID: String, fileURL: URL,
                 mimeType: String = "application/octet-stream") async throws -> FileAttachment {
        let data = try Data(contentsOf: fileURL)
        return try await scope.http.postMultipart(
            scope.path("/measurements/\(measurementUUID)/files/"),
            fields: [:],
            files: [(name: "file", filename: fileURL.lastPathComponent, mimeType: mimeType, data: data)],
            as: FileAttachment.self)
    }

    /// Stream the full history for a point, following cursor pages.
    func iterForPoint(pointId: Int, createdFrom: String? = nil, createdTo: String? = nil,
                      pageSize: Int = 100) -> AsyncThrowingStream<Measurement, Error> {
        let scope = self.scope
        return AsyncThrowingStream { continuation in
            Task {
                var cursor: String? = ""
                do {
                    while true {
                        var q: [URLQueryItem] = [
                            URLQueryItem(name: "cursor", value: cursor),
                            URLQueryItem(name: "limit", value: String(pageSize)),
                            URLQueryItem(name: "created_from", value: createdFrom),
                            URLQueryItem(name: "created_to", value: createdTo),
                        ]
                        // keep cursor="" so the API selects cursor mode
                        q = q.filter { $0.name == "cursor" || ($0.value != nil && $0.value != "") }
                        let page = try await scope.http.get(
                            scope.path("/measurement-points/\(pointId)/measurements/"),
                            query: q, as: CursorPage<Measurement>.self)
                        for m in page.items { continuation.yield(m) }
                        guard let next = page.nextCursor, !next.isEmpty else { break }
                        cursor = next
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }
}
```
> NOTE: `HTTPClient.url(path:query:)` filters out empty query values; to force cursor mode the iterator keeps `cursor` even when empty. If the live API does not accept an empty `cursor`, change the first request to omit `cursor` and switch to cursor mode once `next_cursor` appears — verify against PR-154 during execution.

Also add `createdFrom`/`createdTo` to `listForPoint`:
```swift
    public func listForPoint(pointId: Int, limit: Int = 50, offset: Int = 0,
                             createdFrom: String? = nil, createdTo: String? = nil) async throws -> [Measurement] {
        let q = [
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
            URLQueryItem(name: "created_from", value: createdFrom),
            URLQueryItem(name: "created_to", value: createdTo),
        ]
        return try await scope.http.get(
            scope.path("/measurement-points/\(pointId)/measurements/"),
            query: q, as: Page<Measurement>.self).items
    }
```

- [ ] **Step 4: Run + full suite**

Run: `cd swift && swift test`
Expected: PASS (existing + RegistryTests).

- [ ] **Step 5: Commit**
```bash
git add swift/
git commit -m "feat(swift): batch measurements, file attach, cursor history"
```

---

## Phase 4 — Kotlin

Work dir: `kotlin/`. Run tests with `cd kotlin && ./gradlew test`.

### Task 4.1: Kotlin models + errors + version + tokenless

**Files:**
- Modify: `kotlin/src/main/kotlin/com/arpedon/mechbase/Models.kt`
- Modify: `kotlin/src/main/kotlin/com/arpedon/mechbase/Errors.kt`
- Modify: `kotlin/src/main/kotlin/com/arpedon/mechbase/Http.kt`
- Modify: `kotlin/build.gradle.kts`
- Modify: `kotlin/src/test/kotlin/com/arpedon/mechbase/MechbaseClientTest.kt` (User-Agent assertion)

- [ ] **Step 1: Extend/add models** in `Models.kt` — update `Asset`, `MeasurementPoint`, `Measurement`, add new data classes + cursor wrapper:
```kotlin
@Serializable
data class Asset(
    val uuid: String,
    @SerialName("asset_id") val assetId: Int? = null,
    val name: String,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("machine_class") val machineClass: String = "",
    @SerialName("equipment_type") val equipmentType: String = "",
    val status: Int,
    @SerialName("external_id") val externalId: String? = null,
)
```
Add `@SerialName("external_id") val externalId: String? = null` to `MeasurementPoint` and `Measurement`. Append:
```kotlin
@Serializable
data class Section(
    val uuid: String,
    @SerialName("section_id") val sectionId: Int? = null,
    val name: String,
    @SerialName("external_id") val externalId: String? = null,
)

@Serializable
data class Zone(
    val uuid: String,
    @SerialName("zone_id") val zoneId: Int? = null,
    val name: String,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("external_id") val externalId: String? = null,
)

@Serializable
data class DeleteResult(val deleted: Boolean, val uuid: String)

@Serializable
data class BatchItemResult(
    val index: Int,
    val status: String,
    @SerialName("measurement_point_id") val measurementPointId: Int? = null,
    @SerialName("point_sequence") val pointSequence: Int? = null,
    val uuid: String? = null,
    @SerialName("external_id") val externalId: String? = null,
    val detail: String? = null,
)

@Serializable
data class BatchResult(
    val created: Int,
    val duplicates: Int,
    val errors: Int,
    val results: List<BatchItemResult>,
)

@Serializable
data class FileAttachment(
    val uuid: String,
    val name: String,
    val kind: String,
    @SerialName("file_url") val fileUrl: String,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class MeasurementResult(
    @SerialName("mapping_uuid") val mappingUuid: String,
    val ok: Boolean,
    @SerialName("measurement_uuid") val measurementUuid: String? = null,
    @SerialName("local_uuid") val localUuid: String = "",
    val error: String = "",
)

@Serializable
internal data class PaginatedSections(
    val items: List<Section>, val total: Int = 0, val limit: Int = 0, val offset: Int = 0,
)

@Serializable
internal data class PaginatedZones(
    val items: List<Zone>, val total: Int = 0, val limit: Int = 0, val offset: Int = 0,
)

@Serializable
internal data class CursorMeasurements(
    val items: List<Measurement>,
    @SerialName("next_cursor") val nextCursor: String? = null,
)
```

- [ ] **Step 2: Add exceptions + mapping** in `Errors.kt`:
```kotlin
/** 409. */
class ConflictException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)

/** 413. */
class PayloadTooLargeException(message: String, status: Int? = null, body: String? = null) :
    MechbaseException(message, status, body)
```
In `Http.kt` `handle`, extend the `when`:
```kotlin
            401, 403 -> AuthException(message, code, text)
            404 -> NotFoundException(message, code, text)
            409 -> ConflictException(message, code, text)
            413 -> PayloadTooLargeException(message, code, text)
            422 -> ValidationException(message, code, text)
            else -> ServerException(message, code, text)
```

- [ ] **Step 3: Version bump** in `Http.kt` — change the User-Agent header to `"mechbase-kotlin/0.2"`. (Kotlin has no maintnode client, so no tokenless path is needed; `token` stays `String`.)

- [ ] **Step 4: Add a verb helper for PUT/PATCH/DELETE** — in `Http.kt` add a method that takes an HTTP method name:
```kotlin
    suspend fun <T> sendJson(
        method: String,
        path: String,
        payload: JsonElement?,
        params: Map<String, Any?>? = null,
        serializer: KSerializer<T>,
    ): T = withContext(Dispatchers.IO) {
        val rb: RequestBody? = payload?.let {
            SDK_JSON.encodeToString(JsonElement.serializer(), it).toRequestBody(JSON_MEDIA)
        }
        val builder = baseRequest(buildUrl(path, params))
        val request = when (method) {
            "PUT" -> builder.put(rb ?: "".toRequestBody(JSON_MEDIA))
            "PATCH" -> builder.patch(rb ?: "".toRequestBody(JSON_MEDIA))
            "DELETE" -> if (rb != null) builder.delete(rb) else builder.delete()
            else -> error("unsupported method $method")
        }.build()
        ok.newCall(request).execute().use { resp ->
            val body = handle(resp)
            if (body.isEmpty()) {
                @Suppress("UNCHECKED_CAST")
                Unit as T
            } else {
                SDK_JSON.decodeFromString(serializer, body)
            }
        }
    }
```

- [ ] **Step 5: Bump gradle version + test assertion** — in `kotlin/build.gradle.kts` set `version = "0.2.0"` (if a `version =` line exists; otherwise add it under the plugins/group). In `MechbaseClientTest.kt`, change the assertion to `"mechbase-kotlin/0.2"`.

- [ ] **Step 6: Build**

Run: `cd kotlin && ./gradlew compileKotlin compileTestKotlin`
Expected: compiles.

- [ ] **Step 7: Commit**
```bash
git add kotlin/
git commit -m "feat(kotlin): models, conflict/too-large exceptions, put/patch/delete verbs, v0.2"
```

### Task 4.2: Kotlin registry CRUD

**Files:**
- Modify: `kotlin/.../Assets.kt`, `.../MeasurementPoints.kt`
- Create: `kotlin/.../Sections.kt`, `kotlin/.../Zones.kt`
- Modify: `kotlin/.../Installation.kt`
- Test: `kotlin/src/test/kotlin/com/arpedon/mechbase/RegistryTest.kt` (new)

- [ ] **Step 1: Write a failing test** — create `kotlin/src/test/kotlin/com/arpedon/mechbase/RegistryTest.kt`:
```kotlin
package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class RegistryTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    @Test fun createAsset() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"a-1","asset_id":7,"name":"Pump 7","section_id":3,"zone_id":2,
                "machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}""".trimIndent()))
        val a = client.forInstallation(2012).assets.create(AssetInput(name = "Pump 7", externalId = "P-7"))
        assertEquals(7, a.assetId)
        assertEquals("pump", a.equipmentType)
        val rec = server.takeRequest()
        assertEquals("POST", rec.method)
        assertEquals("/api/installations/2012/assets", rec.path)
    }

    @Test fun conflictRaises() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(409).setHeader("Content-Type", "application/json").setBody("""{"detail":"dup"}"""))
        try {
            client.forInstallation(2012).assets.create(AssetInput(externalId = "P-7"))
            org.junit.Assert.fail("expected ConflictException")
        } catch (e: ConflictException) {
            assertEquals(409, e.status)
        }
        Unit
    }
}
```

- [ ] **Step 2: Run — expect failure**

Run: `cd kotlin && ./gradlew test --tests '*RegistryTest.createAsset'`
Expected: FAIL — `AssetInput`/`create` unresolved.

- [ ] **Step 3: Rewrite `Assets.kt`** with input + write methods:
```kotlin
package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AssetInput(
    val name: String? = null,
    @SerialName("external_id") val externalId: String? = null,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_external_id") val sectionExternalId: String? = null,
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("zone_external_id") val zoneExternalId: String? = null,
    @SerialName("equipment_type") val equipmentType: String? = null,
    @SerialName("machine_class") val machineClass: String? = null,
)

class Assets internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    suspend fun list(q: String? = null, zoneId: Int? = null, limit: Int = 50, offset: Int = 0): List<Asset> =
        http.getJson(
            installationPath(installationId, "/assets"),
            mapOf("q" to q, "zone_id" to zoneId, "limit" to limit, "offset" to offset),
            PaginatedAssets.serializer(),
        ).items

    suspend fun get(assetId: Int): Asset =
        http.getJson(installationPath(installationId, "/assets/$assetId"), null, Asset.serializer())

    suspend fun create(input: AssetInput): Asset =
        http.postJson(installationPath(installationId, "/assets"),
            SDK_JSON.encodeToJsonElement(AssetInput.serializer(), input), Asset.serializer())

    suspend fun upsert(input: AssetInput): Asset =
        http.sendJson("PUT", installationPath(installationId, "/assets"),
            SDK_JSON.encodeToJsonElement(AssetInput.serializer(), input), null, Asset.serializer())

    suspend fun update(assetId: Int, input: AssetInput): Asset =
        http.sendJson("PATCH", installationPath(installationId, "/assets/$assetId"),
            SDK_JSON.encodeToJsonElement(AssetInput.serializer(), input), null, Asset.serializer())

    suspend fun delete(assetId: Int, cascade: Boolean = false): DeleteResult =
        http.sendJson("DELETE", installationPath(installationId, "/assets/$assetId"),
            null, if (cascade) mapOf("cascade" to "true") else null, DeleteResult.serializer())
}
```
> NOTE: `postJson` currently takes a `JsonElement?`; `SDK_JSON.encodeToJsonElement` produces it and (because `SDK_JSON` sets `explicitNulls = false`) nulls are dropped. Add `import kotlinx.serialization.json.JsonElement` where needed; `encodeToJsonElement` is on `SDK_JSON`.

- [ ] **Step 4: Rewrite `MeasurementPoints.kt`** analogously — add `PointInput` (fields per Shared Reference, snake_case `@SerialName`s), keep `list`/`get`, add `create`/`upsert`/`update`/`delete` against `/measurement-points` and `/measurement-points/$pointId`.

- [ ] **Step 5: Create `Sections.kt` and `Zones.kt`** mirroring `Assets.kt`:
  - `SectionInput(name, externalId)`; resource `Sections` with list (`q/limit/offset`, `PaginatedSections`), get, create/upsert/update/delete on `/sections`, `/sections/$sectionId`; returns `Section`.
  - `ZoneInput(name, externalId, sectionId, sectionExternalId)`; resource `Zones` with list (`q/section_id/limit/offset`, `PaginatedZones`), get, CRUD on `/zones`, `/zones/$zoneId`; returns `Zone`.

- [ ] **Step 6: Wire into `Installation.kt`** — add `val sections: Sections = Sections(http, installationId)` and `val zones: Zones = Zones(http, installationId)`.

- [ ] **Step 7: Run**

Run: `cd kotlin && ./gradlew test --tests '*RegistryTest'`
Expected: PASS.

- [ ] **Step 8: Commit**
```bash
git add kotlin/
git commit -m "feat(kotlin): registry CRUD for assets, points, sections, zones"
```

### Task 4.3: Kotlin batch, file attach, cursor history

**Files:**
- Modify: `kotlin/.../Measurements.kt`
- Test: `kotlin/src/test/kotlin/com/arpedon/mechbase/RegistryTest.kt`

- [ ] **Step 1: Write failing tests** — append to `RegistryTest.kt`:
```kotlin
    @Test fun createBatch() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"created":1,"duplicates":0,"errors":0,"results":[
                {"index":0,"status":"created","measurement_point_id":1,"point_sequence":5,
                 "uuid":"m-1","external_id":"E-0","detail":null}]}""".trimIndent()))
        val res = client.forInstallation(2012).measurements.createBatch(listOf(
            MeasurementInput(measurementPointId = 1, data = mapOf("rms" to 2.3), externalId = "E-0")))
        assertEquals(1, res.created)
        assertEquals("created", res.results[0].status)
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/measurements/batch/", rec.path)
    }

    @Test fun iterForPoint() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"items":[{"uuid":"m-1","measurement_point_id":42,"point_sequence":1,
                "data":{},"status":"good","notes":"","created_at":"t1"}],"next_cursor":"CUR2"}""".trimIndent()))
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"items":[{"uuid":"m-2","measurement_point_id":42,"point_sequence":2,
                "data":{},"status":"good","notes":"","created_at":"t2"}],"next_cursor":null}""".trimIndent()))
        val got = mutableListOf<String>()
        client.forInstallation(2012).measurements.iterForPoint(42, pageSize = 1)
            .collect { got.add(it.uuid) }
        assertEquals(listOf("m-1", "m-2"), got)
    }
```

- [ ] **Step 2: Run — expect failure**

Run: `cd kotlin && ./gradlew test --tests '*RegistryTest.createBatch'`
Expected: FAIL — `MeasurementInput`/`createBatch` unresolved.

- [ ] **Step 3: Extend `Measurements.kt`** — add the input type, `createBatch`, `addFile`, `iterForPoint` (a `Flow`), and date filters on `listForPoint`:
```kotlin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject

@Serializable
data class MeasurementInput(
    @SerialName("measurement_point_id") val measurementPointId: Int? = null,
    @SerialName("measurement_point_external_id") val measurementPointExternalId: String? = null,
    val data: JsonObject,
    val notes: String? = null,
    @SerialName("session_id") val sessionId: String? = null,
    val timestamp: String? = null,
    @SerialName("external_id") val externalId: String? = null,
) {
    constructor(
        measurementPointId: Int? = null,
        measurementPointExternalId: String? = null,
        data: Map<String, Any?>,
        notes: String? = null,
        sessionId: String? = null,
        timestamp: String? = null,
        externalId: String? = null,
    ) : this(measurementPointId, measurementPointExternalId, data.toJsonObject(),
             notes, sessionId, timestamp, externalId)
}

@Serializable
private data class BatchBody(val items: List<MeasurementInput>)
```
Then methods on the `Measurements` class:
```kotlin
    suspend fun createBatch(items: List<MeasurementInput>): BatchResult =
        http.postJson(
            installationPath(installationId, "/measurements/batch/"),
            SDK_JSON.encodeToJsonElement(BatchBody.serializer(), BatchBody(items)),
            BatchResult.serializer(),
        )

    suspend fun addFile(measurementUuid: String, file: java.io.File): FileAttachment =
        http.postMultipart(
            installationPath(installationId, "/measurements/$measurementUuid/files/"),
            buildJsonObject { },
            listOf(MultipartFile("file", file.name, file)),
            FileAttachment.serializer(),
        )

    suspend fun listForPoint(
        pointId: Int, limit: Int = 50, offset: Int = 0,
        createdFrom: String? = null, createdTo: String? = null,
    ): List<Measurement> =
        http.getJson(
            installationPath(installationId, "/measurement-points/$pointId/measurements/"),
            mapOf("limit" to limit, "offset" to offset,
                  "created_from" to createdFrom, "created_to" to createdTo),
            PaginatedMeasurements.serializer(),
        ).items

    fun iterForPoint(
        pointId: Int, createdFrom: String? = null, createdTo: String? = null, pageSize: Int = 100,
    ): Flow<Measurement> = flow {
        var cursor: String? = ""
        val path = installationPath(installationId, "/measurement-points/$pointId/measurements/")
        while (true) {
            val params = mutableMapOf<String, Any?>("limit" to pageSize, "cursor" to cursor)
            if (createdFrom != null) params["created_from"] = createdFrom
            if (createdTo != null) params["created_to"] = createdTo
            val page = http.getJson(path, params, CursorMeasurements.serializer())
            page.items.forEach { emit(it) }
            val next = page.nextCursor
            if (next.isNullOrEmpty()) break
            cursor = next
        }
    }
```
> NOTE: `buildUrl` in `Http.kt` skips params whose `toString()` is empty, so `cursor=""` is dropped on the first request. That is fine if the API returns a cursor page whenever `next_cursor` is meaningful; if the live PR-154 API requires an explicit empty `cursor` to enter cursor mode, adjust `buildUrl` to allow an explicit empty value for `cursor`, or send a sentinel — verify during execution. The existing `postMultipart` always adds a `payload` form field; for `addFile` an empty `payload` is harmless, but if PR-154 rejects extra fields, add a `postMultipartNoPayload` variant.

- [ ] **Step 4: Run + full suite**

Run: `cd kotlin && ./gradlew test`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add kotlin/
git commit -m "feat(kotlin): batch measurements, file attach, cursor history"
```

> The maintnode client is **Python + Go only** (per the design); Kotlin/Swift stop here.

---

## Phase 5 — Docs, examples, and final verification

### Task 5.1: README + Go example

**Files:**
- Modify: `README.md`
- Create: `go/examples/sync_registry/main.go`

- [ ] **Step 1: Update `README.md`** — under "What the SDK lets you do", add a bullet for registry sync and batch push, and add a Python snippet showing `inst.sections.upsert(...)`, `inst.assets.upsert(...)`, `inst.measurements.create_batch([...])`. Add a one-line note that the maintnode device client (`MaintNode` / `NewMaintNode`) is available in Python and Go.

- [ ] **Step 2: Create `go/examples/sync_registry/main.go`** mirroring the Python example: `Upsert` a section/zone/asset/point by external id, then `CreateBatch` one reading. Use `mechbase.New(token, "")` and `ptr()` helpers inline.

- [ ] **Step 3: Verify the Go example compiles**

Run: `cd go && go build ./...`
Expected: clean.

- [ ] **Step 4: Commit**
```bash
git add README.md go/examples/
git commit -m "docs: README + Go registry-sync example for the expanded surface"
```

### Task 5.2: Full cross-language verification

- [ ] **Step 1: Run every suite**

Run:
```bash
cd /Users/tsangiotis/dev/mechbase/mechbase-sdk
(cd python && .venv/bin/pytest -q) && \
(cd go && go test ./...) && \
(cd swift && swift test) && \
(cd kotlin && ./gradlew test)
```
Expected: all green.

- [ ] **Step 2: Confirm version bumps**

Run:
```bash
grep -R "mechbase-python/0.2\|mechbase-go/0.2\|mechbase-swift/0.2\|mechbase-kotlin/0.2" python go swift kotlin
grep "version" python/pyproject.toml
```
Expected: a User-Agent hit in each language; pyproject shows `0.2.0`.

- [ ] **Step 3: Final commit (if anything outstanding)**
```bash
git add -A && git commit -m "chore: finalize PR-154 SDK expansion" || echo "nothing to commit"
```

---

## Self-Review notes (for the implementer)

- **Cursor pagination assumption:** `iter_for_point` starts with `cursor=""` to opt into cursor mode and follows `next_cursor`. The exact trigger (empty cursor vs. a sentinel) is **not provable offline** — verify against the live PR-154 endpoint with a real token during execution and adjust if the first page comes back as an offset page. This is called out in the Python, Swift, and Kotlin tasks.
- **`ListForPoint` signature change (Go):** Task 2.3 changes it to an options struct — Task 2.3 Step 4 updates callers. The Python/Swift/Kotlin equivalents keep their old positional/named params and only add optional filters, so they are non-breaking there.
- **Multipart `payload` field (Kotlin):** the existing `postMultipart` always writes a `payload` field; `addFile` sends an empty one. If PR-154's file endpoints reject unknown fields, add a no-payload multipart variant (noted in Task 4.3).
- **Maintnode scope:** Python + Go only (Tasks 1.5, 2.4). Swift/Kotlin intentionally omit it.
</content>
