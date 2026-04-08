from __future__ import annotations

from ._http import HttpClient
from .models import Me
from .resources.measurements import Measurements
from .resources.registry import Assets, MeasurementPoints
from .resources.routes import Routes


class InstallationHandle:
    """All resources scoped to a single installation."""

    def __init__(self, http: HttpClient, installation_id: int):
        self._http = http
        self.installation_id = installation_id
        self.assets = Assets(http, installation_id)
        self.measurement_points = MeasurementPoints(http, installation_id)
        self.measurements = Measurements(http, installation_id)
        self.routes = Routes(http, installation_id)


class Mechbase:
    """Top-level client.

    Usage::

        from mechbase import Mechbase

        client = Mechbase(token="...")  # defaults to https://app.mechbase.io
        me = client.me()
        inst = client.for_installation(me.current_installation_id)
        inst.measurements.create(point_id=1, data={"rms": 2.3})
    """

    DEFAULT_BASE_URL = "https://app.mechbase.io"

    def __init__(self, *, token: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self._http = HttpClient(token=token, base_url=base_url, timeout=timeout)

    def me(self) -> Me:
        return Me.from_dict(self._http.request("GET", "/api/me/"))

    def for_installation(self, installation_id: int) -> InstallationHandle:
        return InstallationHandle(self._http, installation_id)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
