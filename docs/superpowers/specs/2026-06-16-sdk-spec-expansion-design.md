# Design — SDK expansion for the PR-154 API spec

**Date:** 2026-06-16
**Status:** Approved
**Spec source:** `https://pr-154.mechbase.io/api/openapi.json` (saved as `openapi.new.json`, to become `openapi.json`)

## Background

The live API grew from 22 to 46 operations. The mechbase-sdk repo ships four
hand-written clients (Python, Go, Swift, Kotlin) that match `openapi.json` — no
codegen. This design brings the SDK forward to the new spec.

The 24 new operations group as:

1. **Registry CRUD** — POST/PUT/PATCH/DELETE for assets, measurement-points,
   sections, zones.
2. **Batch measurements** — `POST /measurements/batch/`.
3. **Files + richer history** — `POST /measurements/{uuid}/files/`, plus cursor
   pagination and date filters on the point-history list.
4. **Maintnode device API** — `config/heartbeat/measurements/file` under
   `/api/maintnode/{node_uuid}/` (no bearer auth; identified by `node_uuid`).
5. **Login** (`POST /api/auth/login`) and **legacy-redirects** —
   **out of scope** (see Decisions).

## Decisions

- **Login is excluded.** `LoginOut` is `{ok, redirect}` — a session-cookie web
  login, not a token issuer, so it is useless for a bearer-token SDK.
- **legacy-redirects is excluded** — niche URL-migration helper, no SDK value.
- **Language coverage:** the user-token surface (registry CRUD, batch, files,
  richer history) ships in **all four** languages, uniform. The **maintnode
  device client** ships in **Python + Go only** — edge agents run there
  (`HeartbeatIn.balena_uuid` → Linux edge devices); a device-agent surface does
  not belong in the mobile SDKs.
- **Versions bump `0.1 → 0.2`** across all four packages.
- **Error body unchanged:** `ErrorOut` is still `{detail}`, so existing parsing
  holds.

## 1. Registry resources — full CRUD (all four languages)

Four resources on the installation handle: `assets`, `measurement_points`,
**`sections` (new)**, **`zones` (new)**. Sections and zones had GET endpoints in
the API but were never surfaced in the SDK; assets and points gain write methods.

Each resource exposes:

| method | HTTP | result | notes |
|---|---|---|---|
| `list` | GET | `[Out]` | existing for assets/points; new for sections/zones |
| `get(id)` | GET | `Out` | existing for assets/points; new for sections/zones |
| `create(input)` | POST | `Out` (201) | |
| `upsert(input)` | PUT | `Out` (200/201) | keyed by `external_id` |
| `update(id, input)` | PATCH | `Out` (200) | partial update |
| `delete(id, cascade=False)` | DELETE | `DeleteResult` | `cascade` query param |

Input objects mirror the `*In` schemas — **all fields optional**, parents
addressable by **internal id OR external_id** (the registry-sync story):

- **AssetInput**: `name, external_id, section_id, section_external_id, zone_id,
  zone_external_id, equipment_type, machine_class`
- **PointInput**: `name, external_id, asset_id, asset_external_id,
  transducer_type, measurement_unit_code, location, body_segment, body_angle,
  machine_class`
- **SectionInput**: `name, external_id`
- **ZoneInput**: `name, external_id, section_id, section_external_id`

Idiomatic per language: Python keyword args; Go/Swift/Kotlin an input
struct / data class with optional fields. Only non-null fields are serialized so
PATCH stays partial.

### Model changes

- `Asset` += `section_id`, `equipment_type`, `external_id`
- `MeasurementPoint` += `external_id`
- new `Section{uuid, section_id, name, external_id}`
- new `Zone{uuid, zone_id, name, section_id, external_id}`
- new `DeleteResult{deleted, uuid}`

(`AssetOut`/`SectionOut`/`ZoneOut`/`MeasurementPointOut` are the response shapes;
list endpoints keep their existing offset pagination — `{items, total, limit,
offset}`.)

## 2. Batch measurements (all four languages)

`inst.measurements.create_batch(items)` → `POST /measurements/batch/`.

- **item** (MeasurementInput): `measurement_point_id` **or**
  `measurement_point_external_id` (one required), `data` (required), and optional
  `notes, session_id, timestamp, external_id`.
- **returns** `BatchResult{created, duplicates, errors,
  results:[BatchItemResult{index, status, measurement_point_id, point_sequence,
  uuid, external_id, detail}]}`.

Python accepts a list of dicts or `MeasurementInput`; the other languages take a
list of `MeasurementInput`.

## 3. Files + richer history (all four languages)

- `inst.measurements.add_file(measurement_uuid, file)` → multipart
  `POST /measurements/{uuid}/files/` (single form field `file`) →
  `File{uuid, name, kind, file_url, created_at}`. `file` accepts a path or an
  open stream (idiomatic per language).
- `list_for_point` gains optional `created_from` / `created_to` (ISO-8601
  strings); **still returns a list** (offset mode) — non-breaking.
- **New** `iter_for_point(point_id, created_from=, created_to=, page_size=)`:
  follows `next_cursor` until exhausted, yielding every measurement. The list
  endpoint returns a cursor page (`{items, next_cursor}`) when a `cursor` is
  supplied and an offset page otherwise; the iterator drives the cursor variant.
  - Python: generator (`Iterator[Measurement]`)
  - Go: `IterForPoint(ctx, …, func(Measurement) error)` callback (or
    `iter.Seq` if the toolchain allows)
  - Swift: `AsyncSequence` / `AsyncThrowingStream`
  - Kotlin: `Flow<Measurement>`

### Model changes

- `Measurement` += `external_id`

## 4. Maintnode device client (Python + Go only)

A separate top-level client. **No token**; `node_uuid` lives in the path. Achieved
by letting the HTTP layer omit the `Authorization` header when constructed
without a token.

```python
from mechbase import MaintNode

node = MaintNode(node_uuid="…", base_url="https://app.mechbase.io")
node.config()                                   # -> str (raw config blob)
node.heartbeat(balena_uuid="…", services={…})   # -> dict
node.push_measurements([                         # -> [MeasurementResult]
    {"mapping_uuid": "…", "data": {…}},
])
node.add_measurement_file(measurement_uuid, file)  # multipart, field "file"
```

- **HeartbeatIn**: `balena_uuid, services`
- **MaintNodeMeasurementIn**: `mapping_uuid` (required), `data` (required),
  `timestamp?`, `local_uuid?`
- **MeasurementResult**: `mapping_uuid, ok, measurement_uuid, local_uuid, error`
- `config()` returns the raw config string (the endpoint emits a JSON string).

Go: `mechbase.NewMaintNode(nodeUUID, …opts)` with `Config`, `Heartbeat`,
`PushMeasurements`, `AddMeasurementFile`.

## 5. Error handling

`ErrorOut` is `{detail}`, so existing message parsing is unchanged. Across all
clients:

- Add **`ConflictError`** for 409 (e.g. duplicate `external_id`) in all four
  clients.
- Add **`PayloadTooLargeError`** for 413 (file upload too large) in all four
  clients.
- Both new error types subclass the existing base error
  (`MechbaseError` / equivalent) so existing `catch`-the-base code keeps working.
- Treat **201** as success (current handlers key on the 2xx range, so verify each
  language already does).

## 6. Housekeeping

- Replace committed `openapi.json` with the PR-154 version; delete
  `openapi.new.json`.
- Update `README.md` and per-language `examples/` to show registry CRUD and
  batch push.
- Extend each language's mock/HTTP-stub tests to cover the new methods.
- Bump package versions `0.1 → 0.2` (Python `pyproject.toml`, Go module doc/tag
  note, Swift, Kotlin `build.gradle.kts`), and the `User-Agent` strings.

## Out of scope

- `POST /api/auth/login`
- `GET /api/installations/{id}/legacy-redirects`
- Any codegen — clients stay hand-written.

## Testing strategy

Each language already has a mock-transport test (`test_client.py`,
`client_test.go`, `MechbaseTests.swift`, etc.). Extend those with stubbed
responses for: a create + upsert + update + delete round-trip on one registry
resource; a batch push asserting the request body and parsed `BatchResult`; a
cursor iteration that spans two pages; and (Python/Go) a maintnode
`push_measurements` call. No live API calls in tests.
