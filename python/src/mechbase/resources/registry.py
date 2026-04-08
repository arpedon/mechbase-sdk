from __future__ import annotations

from ..models import Asset, MeasurementPoint
from ._base import InstallationScoped, _paginated


class Assets(InstallationScoped):
    def list(self, *, q: str = "", zone_id: int | None = None, limit: int = 50, offset: int = 0) -> list[Asset]:
        return _paginated(
            self._http,
            self._path("/assets"),
            params={"q": q, "zone_id": zone_id, "limit": limit, "offset": offset},
            parse=Asset.from_dict,
        )

    def get(self, asset_id: int) -> Asset:
        return Asset.from_dict(self._http.request("GET", self._path(f"/assets/{asset_id}")))


class MeasurementPoints(InstallationScoped):
    def list(
        self,
        *,
        q: str = "",
        asset_id: int | None = None,
        transducer_type: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> list[MeasurementPoint]:
        return _paginated(
            self._http,
            self._path("/measurement-points"),
            params={
                "q": q,
                "asset_id": asset_id,
                "transducer_type": transducer_type,
                "limit": limit,
                "offset": offset,
            },
            parse=MeasurementPoint.from_dict,
        )

    def get(self, point_id: int) -> MeasurementPoint:
        return MeasurementPoint.from_dict(
            self._http.request("GET", self._path(f"/measurement-points/{point_id}"))
        )
