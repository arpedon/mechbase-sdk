from __future__ import annotations

from ..models import Conditional
from ._base import InstallationScoped, _clean


class Dashboards(InstallationScoped):
    """Dashboards: sections of tiles, each a point's latest value, status, limits and short trend.
    Reading is for members; every write is staff only (`me().user.is_staff`)."""

    def list(self) -> list[dict]:
        """Each: uuid (null for the automatic board), name, is_default, is_automatic."""
        return self._http.request("GET", self._path("/dashboards"))

    def get(self, dashboard_uuid: str = "default", *, etag: str | None = None) -> Conditional:
        """The board: {uuid, name, is_default, is_automatic, refresh_seconds, readiness, sections[{…, tiles}]}.
        Pass the last `etag` to get `not_modified` instead of the same board again; poll every
        `refresh_seconds`. Timeline intervals still open have end=None (draw to now)."""
        body, tag = self._http.conditional(self._path(f"/dashboards/{dashboard_uuid}"), etag=etag)
        return Conditional(body, tag)

    def create(self, name: str = "") -> dict:
        return self._http.request("POST", self._path("/dashboards"), json={"name": name})

    def update(self, dashboard_uuid: str, *, name: str | None = None, is_default: bool | None = None) -> dict:
        return self._http.request("PATCH", self._path(f"/dashboards/{dashboard_uuid}"),
                                  json=_clean({"name": name, "is_default": is_default}))

    def delete(self, dashboard_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/dashboards/{dashboard_uuid}"))

    def save_automatic(self) -> dict:
        """Copy the automatic board into an editable one."""
        return self._http.request("POST", self._path("/dashboards/save-automatic"))

    def reorder(self, dashboard_uuid: str, sections: list[dict]) -> None:
        """The whole layout: [{"id": section_uuid, "tiles": [tile_uuid, …]}, …] in display order."""
        self._http.request("POST", self._path(f"/dashboards/{dashboard_uuid}/reorder"), json={"sections": sections})

    def add_section(self, dashboard_uuid: str, title: str = "") -> dict:
        return self._http.request("POST", self._path(f"/dashboards/{dashboard_uuid}/sections"), json={"title": title})

    def rename_section(self, dashboard_uuid: str, section_uuid: str, title: str) -> dict:
        return self._http.request("PATCH", self._path(f"/dashboards/{dashboard_uuid}/sections/{section_uuid}"),
                                  json={"title": title})

    def delete_section(self, dashboard_uuid: str, section_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/dashboards/{dashboard_uuid}/sections/{section_uuid}"))

    def add_tiles(self, dashboard_uuid: str, section_uuid: str, point_ids: list[int]) -> list[dict]:
        return self._http.request("POST", self._path(f"/dashboards/{dashboard_uuid}/tiles"),
                                  json={"section": section_uuid, "point_ids": list(point_ids)})

    def rename_tile(self, dashboard_uuid: str, tile_uuid: str, label: str) -> dict:
        """An empty label goes back to the point's name."""
        return self._http.request("PATCH", self._path(f"/dashboards/{dashboard_uuid}/tiles/{tile_uuid}"),
                                  json={"label": label})

    def remove_tile(self, dashboard_uuid: str, tile_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/dashboards/{dashboard_uuid}/tiles/{tile_uuid}"))
