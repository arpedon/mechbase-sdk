from __future__ import annotations

from urllib.parse import quote

from ..models import Asset, AssetType, DeleteResult, FileAttachment, MeasurementPoint, Section, Zone
from ._base import _UNSET, InstallationScoped, _clean, _paginated, _upload


def locals_no_self(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "self"}


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
               equipment_type: str | None = None, machine_class: str | None = None,
               asset_type: str | None = None) -> Asset:
        return Asset.from_dict(self._http.request("POST", self._path("/assets"), json=_clean(locals_no_self(locals()))))

    def upsert(self, *, name: str | None = None, external_id: str | None = None,
               section_id: int | None = None, section_external_id: str | None = None,
               zone_id: int | None = None, zone_external_id: str | None = None,
               equipment_type: str | None = None, machine_class: str | None = None,
               asset_type: str | None = None) -> Asset:
        return Asset.from_dict(self._http.request("PUT", self._path("/assets"), json=_clean(locals_no_self(locals()))))

    def update(self, asset_id: int, *, name: str | None = None, external_id: str | None = None,
               section_id: int | None = None, section_external_id: str | None = None,
               zone_id: int | None = None, zone_external_id: str | None = None,
               equipment_type: str | None = None, machine_class: str | None = None,
               asset_type: str | None = _UNSET, fed_from: int | None = _UNSET) -> Asset:
        """`asset_type` (a type code) and `fed_from` (the feeding asset's asset_id): omit to leave, None to clear."""
        body = _clean({k: v for k, v in locals().items() if k not in ("self", "asset_id", "asset_type", "fed_from")})
        if asset_type is not _UNSET:
            body["asset_type"] = asset_type
        if fed_from is not _UNSET:
            body["fed_from"] = fed_from
        return Asset.from_dict(self._http.request("PATCH", self._path(f"/assets/{asset_id}"), json=body))

    def delete(self, asset_id: int, *, cascade: bool = False) -> DeleteResult:
        params = {"cascade": "true"} if cascade else None
        return DeleteResult.from_dict(self._http.request("DELETE", self._path(f"/assets/{asset_id}"), params=params))

    def ensure_checklist(self, asset_id: int) -> dict:
        """Create (or find) the asset's checklist route from its type. Returns {route_uuid, created};
        422 if the asset has no type or the type's checklist is empty."""
        return self._http.request("POST", self._path(f"/assets/{asset_id}/checklist"))

    def add_photo(self, asset_id: int, file, *, filename: str = "photo.jpg", uuid: str | None = None) -> FileAttachment:
        """Append a photo to the asset's gallery. A client `uuid` makes retries safe."""
        return FileAttachment.from_dict(_upload(self._http, self._path(f"/assets/{asset_id}/photos/"),
                                                file, filename, _clean({"uuid": uuid}) or None))

    def delete_photo(self, asset_id: int, photo_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/assets/{asset_id}/photos/{photo_uuid}"))

    def rebuild_checklist(self, asset_id: int) -> dict:
        """Re-read the type's checklist into the asset's checks route. Returns {route_uuid, created: False};
        422 once a run was completed, while one is open, or without a checks route or checklist."""
        return self._http.request("POST", self._path(f"/assets/{asset_id}/checklist/rebuild"))

    def flip_production(self, asset_id: int) -> dict:
        """Flip the asset's production state now (running ⇄ stopped). Returns {state: on|off|stale|None, last_ping}."""
        return self._http.request("POST", self._path(f"/assets/{asset_id}/production/flip"))

    def trend(self, asset_id: int, *, type: str | None = None) -> dict:
        """The datasheet trend, in your units: {series[{point_id, name, unit, type, thresholds,
        measurements[{t, v, status, off}]}], production_status[{t, on}], window, empty}.
        `type` narrows to one transducer type (e.g. "VB")."""
        return self._http.request("GET", self._path(f"/assets/{asset_id}/trend"), params=_clean({"type": type}))

    def fault_record(self, asset_id: int, at: str, *, point_id: int | None = None) -> dict:
        """Every point of the asset over `at` (ISO datetime) ± 60 s: {window, trigger_point_id,
        rows[{point_id, name, unit, status, series[{t, v}], thresholds}]}."""
        return self._http.request("GET", self._path(f"/assets/{asset_id}/fault-record"),
                                  params=_clean({"at": at, "point": point_id}))


_POINT_FIELDS = ("nominal_rpm", "bearing", "speed_ratio", "envelope_band_low", "envelope_band_high", "instructions")


def _point_body(fields: dict) -> dict:
    """_clean, except the analysis fields, where None is sent (it clears them) and _UNSET is not."""
    body = _clean({k: v for k, v in fields.items() if k not in _POINT_FIELDS})
    body.update({k: v for k, v in fields.items() if k in _POINT_FIELDS and v is not _UNSET})
    return body


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
               body_angle: int | None = None, machine_class: str | None = None,
               nominal_rpm: int | None = _UNSET, bearing: str | None = _UNSET, speed_ratio: float | None = _UNSET,
               envelope_band_low: int | None = _UNSET, envelope_band_high: int | None = _UNSET,
               instructions: str | None = _UNSET) -> MeasurementPoint:
        """Analysis fields (nominal_rpm, bearing uuid, speed_ratio, envelope band Hz, instructions HTML)
        are sent only when given; None clears one."""
        return MeasurementPoint.from_dict(self._http.request("POST", self._path("/measurement-points"), json=_point_body(locals_no_self(locals()))))

    def upsert(self, *, name: str | None = None, external_id: str | None = None,
               asset_id: int | None = None, asset_external_id: str | None = None,
               transducer_type: str | None = None, measurement_unit_code: str | None = None,
               location: str | None = None, body_segment: int | None = None,
               body_angle: int | None = None, machine_class: str | None = None) -> MeasurementPoint:
        """The analysis fields are not upsertable (the server refuses them on PUT): set them with update()."""
        return MeasurementPoint.from_dict(self._http.request("PUT", self._path("/measurement-points"), json=_clean(locals_no_self(locals()))))

    def update(self, point_id: int, *, name: str | None = None, external_id: str | None = None,
               asset_id: int | None = None, asset_external_id: str | None = None,
               transducer_type: str | None = None, measurement_unit_code: str | None = None,
               location: str | None = None, body_segment: int | None = None,
               body_angle: int | None = None, machine_class: str | None = None,
               nominal_rpm: int | None = _UNSET, bearing: str | None = _UNSET, speed_ratio: float | None = _UNSET,
               envelope_band_low: int | None = _UNSET, envelope_band_high: int | None = _UNSET,
               instructions: str | None = _UNSET) -> MeasurementPoint:
        """Change only the fields given; for the analysis fields None clears one (e.g. bearing=None)."""
        body = _point_body({k: v for k, v in locals().items() if k not in ("self", "point_id")})
        return MeasurementPoint.from_dict(self._http.request("PATCH", self._path(f"/measurement-points/{point_id}"), json=body))

    def delete(self, point_id: int, *, cascade: bool = False) -> DeleteResult:
        params = {"cascade": "true"} if cascade else None
        return DeleteResult.from_dict(self._http.request("DELETE", self._path(f"/measurement-points/{point_id}"), params=params))

    def context(self, point_id: int) -> dict:
        """Run state, staleness, alarm limits and the last 7 days of the point's headline value."""
        return self._http.request("GET", self._path(f"/measurement-points/{point_id}/context"))

    def add_photo(self, point_id: int, file, *, filename: str = "photo.jpg", uuid: str | None = None) -> FileAttachment:
        """Append a photo. The reference photo stays put (see set_reference_photo);
        a point with none shows its first photo."""
        return FileAttachment.from_dict(_upload(self._http, self._path(f"/measurement-points/{point_id}/photos/"),
                                                file, filename, _clean({"uuid": uuid, "keep_reference": "true"})))

    def delete_photo(self, point_id: int, photo_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/measurement-points/{point_id}/photos/{photo_uuid}"))

    def set_reference_photo(self, point_id: int, photo_uuid: str) -> MeasurementPoint:
        return MeasurementPoint.from_dict(self._http.request(
            "PUT", self._path(f"/measurement-points/{point_id}/reference-photo"), json={"uuid": photo_uuid}))

    def create_baseline(self, point_id: int, refit_from: str) -> str:
        """Relearn the point's normal range from readings since `refit_from` (YYYY-MM-DD); runs in the
        background (422 with too few readings: see baseline_preview). Returns the server's message."""
        return self._http.request("POST", self._path(f"/measurement-points/{point_id}/baseline"),
                                  json={"refit_from": refit_from})["detail"]

    def clear_baseline(self, point_id: int) -> str:
        """Back to the standard ISO limits. Returns the server's message."""
        return self._http.request("DELETE", self._path(f"/measurement-points/{point_id}/baseline"))["detail"]

    def baseline_preview(self, point_id: int, *, since: str | None = None) -> dict:
        """{eligible: usable readings since `since`, fit_min: how many a relearn needs}."""
        return self._http.request("GET", self._path(f"/measurement-points/{point_id}/baseline/preview"),
                                  params=_clean({"since": since}))


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
               section_id: int | None = None, section_external_id: str | None = None,
               guest_view: bool | None = None) -> Zone:
        body = _clean({k: v for k, v in locals().items() if k not in ("self", "zone_id")})
        return Zone.from_dict(self._http.request("PATCH", self._path(f"/zones/{zone_id}"), json=body))

    def set_guest_view(self, enabled: bool, *, zone_ids: list[int] | None = None,
                       section_id: int | None = None, all: bool = False) -> int:
        """Turn the QR guest view on/off in one call for exactly one target: zone_ids, a section,
        or all=True for every zone. Returns the number of zones updated."""
        if (zone_ids is not None) + (section_id is not None) + all != 1:
            raise ValueError("Name one of zone_ids, section_id, or all=True.")
        body = _clean({"enabled": enabled, "zone_ids": zone_ids, "section_id": section_id, "all": all or None})
        return self._http.request("POST", self._path("/zones/guest-view"), json=body)["updated"]

    def delete(self, zone_id: int, *, cascade: bool = False) -> DeleteResult:
        params = {"cascade": "true"} if cascade else None
        return DeleteResult.from_dict(self._http.request("DELETE", self._path(f"/zones/{zone_id}"), params=params))

    def documents(self, zone_id: int) -> list[dict]:
        """Each: uuid, name, kind, url, created_at, inherited (from the section: delete it there)."""
        return self._http.request("GET", self._path(f"/zones/{zone_id}/documents"))

    def add_document(self, zone_id: int, file, *, filename: str = "document.pdf", kind: str = "attachment",
                     uuid: str | None = None) -> dict:
        """A client `uuid` makes retries safe."""
        return _upload(self._http, self._path(f"/zones/{zone_id}/documents"), file, filename,
                       _clean({"kind": kind, "uuid": uuid}))

    def delete_document(self, zone_id: int, document_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/zones/{zone_id}/documents/{document_uuid}"))

    def photos(self, zone_id: int) -> list[dict]:
        """Each: uuid, name, url, taken_at, created_at."""
        return self._http.request("GET", self._path(f"/zones/{zone_id}/photos"))

    def add_photo(self, zone_id: int, file, *, filename: str = "photo.jpg", uuid: str | None = None) -> dict:
        """A client `uuid` makes retries safe."""
        return _upload(self._http, self._path(f"/zones/{zone_id}/photos"), file, filename,
                       _clean({"uuid": uuid}) or None)

    def delete_photo(self, zone_id: int, photo_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/zones/{zone_id}/photos/{photo_uuid}"))


class AssetTypes(InstallationScoped):
    """Asset types (templates), addressed by `code`: name, manufacturer, checklist and documents."""

    def _type(self, code: str, suffix: str = "") -> str:
        # Escaped so "/", "?" or "#" in a code cannot address another type.
        if not code:
            raise ValueError("code is required")
        return self._path(f"/asset-types/{quote(code, safe='')}{suffix}")

    def list(self) -> list[AssetType]:
        return [AssetType.from_dict(i) for i in self._http.request("GET", self._path("/asset-types"))]

    def get(self, code: str) -> AssetType:
        return AssetType.from_dict(self._http.request("GET", self._type(code)))

    def upsert(self, code: str, *, name: str | None = None, manufacturer: str | None = None,
               checklist: list[dict] | None = None, external_id: str | None = None) -> AssetType:
        body = _clean({"code": code, "name": name, "manufacturer": manufacturer,
                       "checklist": checklist, "external_id": external_id})
        return AssetType.from_dict(self._http.request("PUT", self._path("/asset-types"), json=body))

    def update(self, code: str, *, name: str | None = None, manufacturer: str | None = None,
               checklist: list[dict] | None = None, external_id: str | None = None) -> AssetType:
        body = _clean({"name": name, "manufacturer": manufacturer, "checklist": checklist, "external_id": external_id})
        return AssetType.from_dict(self._http.request("PATCH", self._type(code), json=body))

    def delete(self, code: str) -> DeleteResult:
        return DeleteResult.from_dict(self._http.request("DELETE", self._type(code)))

    def documents(self, code: str) -> list[dict]:
        """Each: uuid, name, kind, url, created_at."""
        return self._http.request("GET", self._type(code, "/documents"))

    def add_document(self, code: str, file, *, filename: str = "document.pdf", kind: str = "attachment",
                     uuid: str | None = None) -> dict:
        return _upload(self._http, self._type(code, "/documents"), file, filename,
                       _clean({"kind": kind, "uuid": uuid}))

    def delete_document(self, code: str, document_uuid: str) -> None:
        self._http.request("DELETE", self._type(code, f"/documents/{document_uuid}"))
