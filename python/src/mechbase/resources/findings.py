from __future__ import annotations

from ..models import Finding
from ._base import InstallationScoped, _clean


class Findings(InstallationScoped):
    def list(self, *, status: str | None = None, asset_id: int | None = None,
             asset_external_id: str | None = None, point_id: int | None = None,
             point_external_id: str | None = None, since: str | None = None,
             limit: int = 50, cursor: str | None = None) -> list[Finding]:
        """One page of findings, newest first. `status`: open, acknowledged or closed."""
        body = self._http.request("GET", self._path("/findings/"), params=_clean({
            "status": status, "asset_id": asset_id, "asset_external_id": asset_external_id,
            "point_id": point_id, "point_external_id": point_external_id,
            "since": since, "limit": limit, "cursor": cursor,
        }))
        return [Finding.from_dict(i) for i in body["items"]]

    def get(self, finding_uuid: str) -> Finding:
        return Finding.from_dict(self._http.request("GET", self._path(f"/findings/{finding_uuid}/")))

    def acknowledge(self, finding_uuid: str, *, work_order_ref: str) -> Finding:
        """A work order was raised for it; the reference is required."""
        return self._set(finding_uuid, "acknowledged", work_order_ref)

    def close(self, finding_uuid: str, *, work_order_ref: str | None = None) -> Finding:
        """The work is done."""
        return self._set(finding_uuid, "closed", work_order_ref)

    def _set(self, finding_uuid: str, status: str, work_order_ref: str | None) -> Finding:
        body = _clean({"status": status, "work_order_ref": work_order_ref})
        return Finding.from_dict(self._http.request("POST", self._path(f"/findings/{finding_uuid}/status/"), json=body))
