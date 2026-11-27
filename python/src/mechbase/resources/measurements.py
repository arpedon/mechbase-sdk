from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO

from ..models import BatchResult, Conditional, DeleteResult, FileAttachment, Measurement
from ._base import InstallationScoped, _clean, _paginated, _upload


class Measurements(InstallationScoped):
    def create(
        self,
        *,
        point_id: int,
        data: dict,
        notes: str = "",
        session_id: str | None = None,
        timestamp: str | None = None,
        file: str | Path | BinaryIO | None = None,
        idempotency_key: str | None = None,
    ) -> Measurement:
        payload: dict[str, Any] = {
            "measurement_point_id": point_id,
            "data": data,
            "notes": notes,
        }
        if session_id:
            payload["session_id"] = session_id
        if timestamp:
            payload["timestamp"] = timestamp

        headers = {"X-Idempotency-Key": idempotency_key} if idempotency_key else None

        if file is None:
            body = self._http.request(
                "POST", self._path("/measurements/"), json=payload, headers=headers
            )
            return Measurement.from_dict(body)

        fh = file
        opened = False
        if isinstance(file, (str, Path)):
            fh = open(file, "rb")  # noqa: SIM115
            opened = True
        try:
            body = self._http.request(
                "POST",
                self._path("/measurements/upload/"),
                data={"payload": json.dumps(payload)},
                files={"file": (Path(getattr(fh, "name", "attachment")).name, fh)},
                headers=headers,
            )
        finally:
            if opened:
                fh.close()
        return Measurement.from_dict(body)

    def list_for_point(self, point_id: int, *, limit: int = 50, offset: int = 0,
                       created_from: str | None = None, created_to: str | None = None) -> list[Measurement]:
        return _paginated(
            self._http,
            self._path(f"/measurement-points/{point_id}/measurements/"),
            params={"limit": limit, "offset": offset,
                    "created_from": created_from, "created_to": created_to},
            parse=Measurement.from_dict,
        )

    def get(self, point_id: int, point_sequence: int) -> Measurement:
        """One reading, by the number shown in the web URL (…/measurements/766/)."""
        return Measurement.from_dict(
            self._http.request("GET", self._path(f"/measurement-points/{point_id}/measurements/{point_sequence}/"))
        )

    def delete(self, point_id: int, point_sequence: int) -> DeleteResult:
        """Delete one reading; the point's state rolls back to its newest surviving reading."""
        return DeleteResult.from_dict(
            self._http.request("DELETE", self._path(f"/measurement-points/{point_id}/measurements/{point_sequence}/"))
        )

    def set_notes(self, point_id: int, point_sequence: int, notes: str) -> Measurement:
        return Measurement.from_dict(self._http.request(
            "PATCH", self._path(f"/measurement-points/{point_id}/measurements/{point_sequence}/"), json={"notes": notes}))

    def analysis(self, point_id: int, point_sequence: int, *, highpass_hz: float | None = None,
                 lowpass_hz: float | None = None) -> dict:
        """What the web's reading page draws: data (scalars), units, display_units, previous/next_sequence,
        vibration{waveform, spectrum{freq_hz, accel, velocity, envelope}, thresholds, bearing_markers, order,
        n_lines, freq_resolution_hz, source_resolution_hz}, thermography{thermograms, hotspot_count}, attachments.
        Amplitudes are in your units; frequencies in Hz (× units.frequency_scale to show). Waveform x is t_s[]."""
        return self._http.request(
            "GET", self._path(f"/measurement-points/{point_id}/measurements/{point_sequence}/analysis"),
            params=_clean({"highpass_hz": highpass_hz, "lowpass_hz": lowpass_hz}))

    def process(self, point_id: int, point_sequence: int, *, type: str = "velocity", high_pass: float = 0,
                low_pass: float = 0, db_scale: bool = False, peak_count: int = 0,
                cursors: list[int] | None = None) -> dict:
        """The compare panel: type accel|velocity|envelope|waveform, filters (Hz, 0 = off), dB, top peaks.
        `cursors` are up to 8 point_sequences of the same point (default: this one). Returns
        {type, units, cursors[{point_sequence, x, y, peaks[{x, y}]}]}; a foreign sequence comes back empty."""
        body = _clean({"type": type, "high_pass": high_pass, "low_pass": low_pass, "db_scale": db_scale,
                       "peak_count": peak_count, "cursors": cursors})
        return self._http.request(
            "POST", self._path(f"/measurement-points/{point_id}/measurements/{point_sequence}/process"), json=body)

    def compare(self, point_id: int, point_sequences: list[int], *, spectrum: str | None = None,
                etag: str | None = None) -> Conditional:
        """Overlay spectra of up to 8 readings: {point_id, spectrum, units, zoom_range_hz, baseline,
        cursors[{point_sequence, color, metrics, freq_hz, values, markers}]}. Send the last `etag` back
        to get `not_modified` instead of the same data."""
        params = _clean({"seq": ",".join(map(str, point_sequences)), "spectrum": spectrum})
        body, tag = self._http.conditional(self._path(f"/measurement-points/{point_id}/compare"),
                                           etag=etag, params=params)
        return Conditional(body, tag)

    def spectra(self, measurement_uuid: str) -> dict:
        """FFT arrays: freq_hz, velocity, acceleration, envelope (empty without a waveform)."""
        return self._http.request("GET", self._path(f"/analytics/measurements/{measurement_uuid}/spectra/"))

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
        return FileAttachment.from_dict(
            _upload(self._http, self._path(f"/measurements/{measurement_uuid}/files/"), file, filename)
        )

    def set_hotspots(self, measurement_uuid: str, hot_clusters: list[dict]) -> Measurement:
        """Replace a thermal image's marked hot spots."""
        return Measurement.from_dict(self._http.request(
            "PATCH", self._path(f"/measurements/{measurement_uuid}/hotspots/"), json={"hot_clusters": hot_clusters}))

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
