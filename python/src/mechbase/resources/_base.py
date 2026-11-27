from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

if TYPE_CHECKING:
    from .._http import HttpClient


class InstallationScoped:
    """Mixin: holds an HttpClient and an installation_id."""

    def __init__(self, http: "HttpClient", installation_id: int):
        self._http = http
        self._iid = installation_id

    def _path(self, suffix: str) -> str:
        return f"/api/installations/{self._iid}{suffix}"


_UNSET: Any = object()  # omitted argument (send nothing) vs None (send null)


def _paginated(http, path: str, *, params: dict, parse) -> list:
    params = {k: v for k, v in params.items() if v is not None and v != ""}
    body = http.request("GET", path, params=params)
    return [parse(i) for i in body["items"]]


def _clean(d: dict) -> dict:
    """Drop keys whose value is None (keeps PATCH partial)."""
    return {k: v for k, v in d.items() if v is not None}


def _upload(http, path: str, file: "str | Path | BinaryIO | bytes", filename: str, data: dict | None = None):
    """POST one multipart `file` (a path, an open file or bytes) plus form `data`."""
    fh = file
    opened = False
    if isinstance(file, (str, Path)):
        filename = Path(file).name
        fh = open(file, "rb")  # noqa: SIM115
        opened = True
    elif isinstance(file, (bytes, bytearray)):
        fh = io.BytesIO(file)
    try:
        return http.request("POST", path, data=data, files={"file": (filename, fh)})
    finally:
        if opened:
            fh.close()
