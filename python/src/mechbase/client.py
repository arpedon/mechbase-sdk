from __future__ import annotations

from ._http import MAX_RETRIES, HttpClient
from .models import Me, WebSession
from .resources._base import _clean
from .resources.analytics import Exports
from .resources.dashboards import Dashboards
from .resources.devices import Devices, Sources, Tunnels
from .resources.findings import Bearings, Findings
from .resources.measurements import Measurements
from .resources.overview import Activity, NotificationSettings, Push
from .resources.registry import Assets, AssetTypes, MeasurementPoints, Sections, Zones
from .resources.routes import NonConformities, Routes
from .resources.thread import AlarmRules, Comments, Documents


class InstallationHandle:
    """All resources scoped to a single installation."""

    def __init__(self, http: HttpClient, installation_id: int):
        self._http = http
        self.installation_id = installation_id
        self.activity = Activity(http, installation_id)
        self.alarm_rules = AlarmRules(http, installation_id)
        self.assets = Assets(http, installation_id)
        self.asset_types = AssetTypes(http, installation_id)
        self.bearings = Bearings(http, installation_id)
        self.comments = Comments(http, installation_id)
        self.dashboards = Dashboards(http, installation_id)
        self.devices = Devices(http, installation_id)
        self.documents = Documents(http, installation_id)
        self.exports = Exports(http, installation_id)
        self.findings = Findings(http, installation_id)
        self.measurement_points = MeasurementPoints(http, installation_id)
        self.measurements = Measurements(http, installation_id)
        self.non_conformities = NonConformities(http, installation_id)
        self.notification_settings = NotificationSettings(http, installation_id)
        self.routes = Routes(http, installation_id)
        self.sections = Sections(http, installation_id)
        self.sources = Sources(http, installation_id)
        self.zones = Zones(http, installation_id)

    def _get(self, suffix: str, params: dict | None = None):
        return self._http.request("GET", f"/api/installations/{self.installation_id}{suffix}", params=params)

    def legacy_redirects(self) -> list[dict]:
        """Old-platform URLs mapped to their measurement points here."""
        return self._get("/legacy-redirects")["items"]

    def overview(self) -> dict:
        """The web home: status_summary, briefing, last_reading_at, attention (top 6; attention_more_count
        more on alerts()), silent_count, running_executions, routes, back_to_normal, sections."""
        return self._get("/overview")

    def alerts(self, *, silent: bool = False) -> list[dict]:
        """Every asset needing attention (silent=True: every silent asset instead). Each: asset_id, name,
        status, is_silent, reason, trigger_name, trigger_point_id, section/zone names, alert_since."""
        return self._get("/alerts", {"show": "silent"} if silent else None)

    def search(self, q: str, *, in_: str | None = None) -> dict:
        """Counts per category plus typed results (assets, sections, zones, points, routes, route_items,
        comments, item_responses). in_: one category slug (assets, sections, zones, points, routes, items,
        comments, notes) for more rows of it. Under 2 characters finds nothing."""
        return self._get("/search", _clean({"q": q, "in": in_}))

    def hours(self, *, production_from: str | None = None, production_to: str | None = None) -> dict:
        """Running hours of production-tracked assets over local days (ISO dates; neither = today):
        {window_start, window_end, stale_hours, rows[{asset_id, asset_name, state, last_ping, range_hours,
        lifetime_hours, segments}]}."""
        return self._get("/hours", _clean({"production_from": production_from, "production_to": production_to}))


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

    def __init__(self, *, token: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0,
                 max_retries: int = MAX_RETRIES, timezone: str | None = None):
        """timezone: IANA zone sent as X-Timezone on every request, so "today" (dashboards, hours) is
        yours; default this machine's zone, "" sends none."""
        self._http = HttpClient(token=token, base_url=base_url, timeout=timeout, max_retries=max_retries,
                                timezone=timezone)
        self.tunnels = Tunnels(self._http)
        self.push = Push(self._http)

    def me(self) -> Me:
        return Me.from_dict(self._http.request("GET", "/api/me/"))

    def update_me(self, *, first_name: str | None = None, last_name: str | None = None,
                  unit_prefs: dict[str, str] | None = None) -> Me:
        """Change only what is given ("" clears a name). unit_prefs: any of acceleration, velocity,
        temperature, pressure, frequency, e.g. {"velocity": "in/s"}. Not for service tokens."""
        body = _clean({"first_name": first_name, "last_name": last_name, "unit_prefs": unit_prefs})
        return Me.from_dict(self._http.request("PATCH", "/api/me/", json=body))

    def web_session(self, next: str) -> WebSession:
        """A single-use, 60-second link that signs a browser in as this token's user and opens `next`:
        a server path ("/2012/assets/5/") or the https:// URL of a device tunnel you can open
        (anything else: ValidationError). Not for service or installation-scoped tokens."""
        return WebSession.from_dict(self._http.request("POST", "/api/auth/web-session", json={"next": next}))

    def revoke_token(self) -> None:
        """Sign this token out server-side; the client is unusable afterwards."""
        self._http.request("POST", "/api/auth/token/revoke")

    def for_installation(self, installation_id: int) -> InstallationHandle:
        return InstallationHandle(self._http, installation_id)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
