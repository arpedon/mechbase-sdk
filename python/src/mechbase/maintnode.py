from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any, BinaryIO

from ._http import MAX_RETRIES, HttpClient
from .models import MeasurementResult


class MaintNode:
    """Device-facing client for the maintnode integration API.

    The node is identified by ``node_uuid`` in the path and authenticates with its own API token
    (the one the server pushes to it on claim). config, measurements and files need it; heartbeat
    needs it once the device is claimed (an unclaimed device heartbeats without one).

    Usage::

        node = MaintNode(node_uuid="...", token="...")  # defaults to https://app.mechbase.io
        cfg = node.config()
        node.heartbeat(config_version=MaintNode.config_version(cfg))
        node.push_measurements([{"mapping_uuid": "...", "data": {"rms": 2.3}}])
    """

    DEFAULT_BASE_URL = "https://app.mechbase.io"

    def __init__(self, *, node_uuid: str, token: str | None = None, base_url: str = DEFAULT_BASE_URL,
                 timeout: float = 30.0, max_retries: int = MAX_RETRIES):
        self._http = HttpClient(token=token, base_url=base_url, timeout=timeout, max_retries=max_retries)
        self.node_uuid = node_uuid

    def _path(self, suffix: str) -> str:
        return f"/api/maintnode/{self.node_uuid}{suffix}"

    def config(self) -> str:
        """The device.yaml the server generates for this node (exactly as served)."""
        return self._http.request("GET", self._path("/config/"), raw=True).decode()

    @staticmethod
    def config_version(config: str | bytes) -> str:
        """What heartbeat(config_version=) reports: sha256 hex of the config body applied.

        Only a config fetched with the device's own token matches the server's version: the server
        hashes the body it serves the device, tunnels (and their secrets) included, and other tokens
        get it without them."""
        return hashlib.sha256(config.encode() if isinstance(config, str) else config).hexdigest()

    def heartbeat(self, *, balena_uuid: str = "", services: dict | None = None,
                  config_version: str | None = None, hardware: dict | None = None) -> dict:
        """hardware: what the node detected, any of {hat_addresses: [int] (≤8), usb201: bool,
        modbus: [{host, port, unit_id, reachable}] (≤32)}. Out of bounds rejects the whole heartbeat (422)."""
        body: dict[str, Any] = {"balena_uuid": balena_uuid, "services": services or {}}
        if config_version is not None:
            body["config_version"] = config_version
        if hardware is not None:
            body["hardware"] = hardware
        return self._http.request("POST", self._path("/heartbeat/"), json=body)

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
