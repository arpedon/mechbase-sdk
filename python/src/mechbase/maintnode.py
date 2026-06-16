from __future__ import annotations

import io
from pathlib import Path
from typing import Any, BinaryIO

from ._http import HttpClient
from .models import MeasurementResult


class MaintNode:
    """Device-facing client for the maintnode integration API.

    Unauthenticated; the node is identified by ``node_uuid`` in the path.

    Usage::

        node = MaintNode(node_uuid="...")  # defaults to https://app.mechbase.io
        cfg = node.config()
        node.push_measurements([{"mapping_uuid": "...", "data": {"rms": 2.3}}])
    """

    DEFAULT_BASE_URL = "https://app.mechbase.io"

    def __init__(self, *, node_uuid: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self._http = HttpClient(token=None, base_url=base_url, timeout=timeout)
        self.node_uuid = node_uuid

    def _path(self, suffix: str) -> str:
        return f"/api/maintnode/{self.node_uuid}{suffix}"

    def config(self) -> str:
        return self._http.request("GET", self._path("/config/"))

    def heartbeat(self, *, balena_uuid: str = "", services: dict | None = None) -> dict:
        return self._http.request(
            "POST", self._path("/heartbeat/"),
            json={"balena_uuid": balena_uuid, "services": services or {}},
        )

    def push_measurements(self, items: list[dict]) -> list[MeasurementResult]:
        body = self._http.request(
            "POST", self._path("/measurements/"), json={"measurements": list(items)}
        )
        return [MeasurementResult.from_dict(r) for r in body]

    def add_measurement_file(
        self, measurement_uuid: str, *,
        file: str | Path | BinaryIO | bytes, filename: str = "attachment",
    ) -> dict:
        fh: Any = file
        opened = False
        if isinstance(file, (str, Path)):
            filename = Path(file).name
            fh = open(file, "rb")  # noqa: SIM115
            opened = True
        elif isinstance(file, (bytes, bytearray)):
            fh = io.BytesIO(file)
        try:
            return self._http.request(
                "POST", self._path(f"/measurements/{measurement_uuid}/file/"),
                files={"file": (filename, fh)},
            )
        finally:
            if opened:
                fh.close()

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
