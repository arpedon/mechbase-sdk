from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO

from ..models import Measurement
from ._base import InstallationScoped, _paginated


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

        if file is None:
            body = self._http.request(
                "POST", self._path("/measurements/"), json=payload
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
            )
        finally:
            if opened:
                fh.close()
        return Measurement.from_dict(body)

    def list_for_point(self, point_id: int, *, limit: int = 50, offset: int = 0) -> list[Measurement]:
        return _paginated(
            self._http,
            self._path(f"/measurement-points/{point_id}/measurements/"),
            params={"limit": limit, "offset": offset},
            parse=Measurement.from_dict,
        )
