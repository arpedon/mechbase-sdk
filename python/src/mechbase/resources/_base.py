from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._http import HttpClient


class InstallationScoped:
    """Mixin: holds an HttpClient and an installation_id."""

    def __init__(self, http: "HttpClient", installation_id: int):
        self._http = http
        self._iid = installation_id

    def _path(self, suffix: str) -> str:
        return f"/api/installations/{self._iid}{suffix}"


def _paginated(http, path: str, *, params: dict, parse) -> list:
    params = {k: v for k, v in params.items() if v is not None and v != ""}
    body = http.request("GET", path, params=params)
    return [parse(i) for i in body["items"]]
