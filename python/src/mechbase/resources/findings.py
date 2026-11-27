from __future__ import annotations

from ..models import Finding
from ._base import InstallationScoped, _clean


class Findings(InstallationScoped):
    def list(self, *, status: str | None = None, asset_id: int | None = None,
             asset_external_id: str | None = None, point_id: int | None = None,
             point_external_id: str | None = None, since: str | None = None,
             limit: int = 50) -> list[Finding]:
        """Up to `limit` findings, following pages. `status`: open, acknowledged or closed.
        `since` (ISO datetime) returns findings changed after it, for CMMS sync."""
        out: list[Finding] = []
        for f in self.iter(status=status, asset_id=asset_id, asset_external_id=asset_external_id,
                           point_id=point_id, point_external_id=point_external_id, since=since,
                           page_size=min(limit, 100)):
            out.append(f)
            if len(out) >= limit:
                break
        return out

    def iter(self, *, status: str | None = None, asset_id: int | None = None,
             asset_external_id: str | None = None, point_id: int | None = None,
             point_external_id: str | None = None, since: str | None = None, page_size: int = 100):
        """Yield every matching finding, following cursor pages."""
        cursor = None
        while True:
            body = self._http.request("GET", self._path("/findings/"), params=_clean({
                "status": status, "asset_id": asset_id, "asset_external_id": asset_external_id,
                "point_id": point_id, "point_external_id": point_external_id,
                "since": since, "limit": page_size, "cursor": cursor,
            }))
            yield from (Finding.from_dict(i) for i in body["items"])
            cursor = body.get("next_cursor")
            if not cursor:
                return

    def create(self, *, point_id: int, point_sequence: int, fault_type: str, severity: str,
               recommended_action: str = "", due_by: str | None = None, comment: str = "",
               hz: float | None = None, amplitude: float | None = None, unit: str = "", signal: str = "",
               shaft_hz: float | None = None, df: float | None = None) -> Finding:
        """Record a finding on a reading. fault_type / severity are values from choices(). The cursor
        (hz, amplitude, unit, signal accel|velocity|envelope, shaft_hz, df = the analysis'
        source_resolution_hz) is stored as evidence."""
        body = _clean({"point_id": point_id, "point_sequence": point_sequence, "fault_type": fault_type,
                       "severity": severity, "recommended_action": recommended_action, "due_by": due_by,
                       "comment": comment, "hz": hz, "amplitude": amplitude, "unit": unit, "signal": signal,
                       "shaft_hz": shaft_hz, "df": df})
        return Finding.from_dict(self._http.request("POST", self._path("/findings/"), json=body))

    def choices(self, *, point_id: int | None = None, point_sequence: int | None = None,
                hz: float | None = None, amplitude: float | None = None, unit: str = "", signal: str = "",
                shaft_hz: float | None = None, df: float | None = None) -> dict:
        """{fault_types[{value, label}], severities[{value, label}], suggested_fault_type, evidence}.
        With a reading and a cursor it also suggests the fault the bearing markers point at."""
        params = _clean({"point_id": point_id, "point_sequence": point_sequence, "hz": hz, "amplitude": amplitude,
                         "unit": unit or None, "signal": signal or None, "shaft_hz": shaft_hz, "df": df})
        return self._http.request("GET", self._path("/findings/choices/"), params=params)

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


class Bearings(InstallationScoped):
    """Bearing defect frequencies: the installation's own bearings plus the shared library (read only)."""

    def search(self, q: str = "", *, order: float | None = None, sideband: str | None = None) -> dict:
        """{own: the installation's bearings (with point_count), results, library_count}. `results`: with `q`
        (≥2 chars) up to 100 by designation/manufacturer; with `order` (a tone's order of shaft speed) up to 8
        whose defect orders match (`sideband` "1x" or "ftf"). Each: uuid, designation, manufacturer, source,
        editable, bpfo, bpfi, bsf, ftf, rolling_elements, …"""
        return self._http.request("GET", self._path("/bearings"),
                                  params=_clean({"q": q or None, "order": order, "sideband": sideband}))

    def get(self, bearing_uuid: str) -> dict:
        return self._http.request("GET", self._path(f"/bearings/{bearing_uuid}"))

    def create(self, designation: str, **fields) -> dict:
        """fields: manufacturer, rolling_elements, bpfo, bpfi, bsf, ftf (orders of shaft speed), ball_diameter,
        pitch_diameter, contact_angle."""
        return self._http.request("POST", self._path("/bearings"), json={"designation": designation, **fields})

    def update(self, bearing_uuid: str, **fields) -> dict:
        """Only an installation bearing (editable); unsent fields keep their value."""
        return self._http.request("PATCH", self._path(f"/bearings/{bearing_uuid}"), json=fields)

    def delete(self, bearing_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/bearings/{bearing_uuid}"))
