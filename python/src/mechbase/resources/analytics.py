from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from ..errors import MechbaseError
from ._base import InstallationScoped


class Exports(InstallationScoped):
    """Async exports of `measurements`, `events` or `inspections` as csv or parquet."""

    def create(self, dataset: str, *, format: str = "csv", filters: dict | None = None) -> dict:
        """Start an export; returns {job_uuid, state, status_url}."""
        payload = {"dataset": dataset, "format": format, "filters": filters or {}}
        return self._http.request("POST", self._path("/analytics/exports/"), json=payload)

    def status(self, job_uuid: str) -> dict:
        """State (pending/running/done/failed/expired), row count and, once done, download_url."""
        return self._http.request("GET", self._path(f"/analytics/exports/{job_uuid}/"))

    def download(self, job_uuid: str) -> bytes:
        """The finished file's bytes (follows the signed download_url)."""
        st = self.status(job_uuid)
        if not st.get("download_url"):
            raise MechbaseError(f"Export {job_uuid} has no file yet ({st.get('state')})", status=410)
        # Keep only the signature; the path resolves against the client's base URL.
        sig = parse_qs(urlsplit(st["download_url"]).query).get("sig", [""])[0]
        return self._http.request("GET", self._path(f"/analytics/exports/{job_uuid}/download/"),
                                  params={"sig": sig}, raw=True)
