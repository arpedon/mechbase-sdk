from __future__ import annotations

from ..models import Asset, DeleteResult, MeasurementPoint, Section, Zone
from ._base import InstallationScoped, _clean, _paginated


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
