from __future__ import annotations

from urllib.parse import quote

from ..errors import NotFoundError
from ._base import InstallationScoped, _clean


class Activity(InstallationScoped):
    """The Activity feed: status changes, notes, findings and route completions, newest first.
    Group by local day client-side."""

    def list(self, *, limit: int = 50, cursor: str | None = None, section_id: int | None = None) -> dict:
        """One page: {items: [{kind, timestamp, title, detail, state, severity, actor, old_status, new_status,
        asset_id, point_id, comment_id, finding_uuid, execution_uuid, route_uuid}], next_cursor}."""
        return self._http.request("GET", self._path("/activity"),
                                  params=_clean({"limit": limit, "cursor": cursor, "section_id": section_id}))

    def iter(self, *, section_id: int | None = None, page_size: int = 100):
        """Yield every entry, following cursor pages (oldest last)."""
        cursor = None
        while True:
            body = self.list(limit=page_size, cursor=cursor, section_id=section_id)
            yield from body["items"]
            cursor = body.get("next_cursor")
            if not cursor:
                return


class NotificationSettings(InstallationScoped):
    """Your e-mail/push notification settings for this installation."""

    def get(self) -> dict:
        """{severity_threshold, status_changes, route_completions, exports, notifications_muted, threshold_choices}."""
        return self._http.request("GET", self._path("/notification-settings"))

    def update(self, *, severity_threshold: int | None = None, status_changes: bool | None = None,
               route_completions: bool | None = None, exports: bool | None = None,
               notifications_muted: bool | None = None) -> dict:
        """Change only the fields given."""
        body = _clean({"severity_threshold": severity_threshold, "status_changes": status_changes,
                       "route_completions": route_completions, "exports": exports,
                       "notifications_muted": notifications_muted})
        return self._http.request("PATCH", self._path("/notification-settings"), json=body)

    def test(self) -> str:
        """Send yourself a test e-mail: "sent", or "logged" where the server has no mail set up."""
        return self._http.request("POST", self._path("/notification-settings/test"))["result"]


class Push:
    """This API token's push registration (one per device token; revoking the API token drops it)."""

    def __init__(self, http):
        self._http = http

    def register(self, platform: str, token: str, *, app_version: str = "") -> dict:
        """platform: "apns" (hex token) or "fcm". Call after sign-in and on every token refresh."""
        return self._http.request("POST", "/api/push/devices",
                                  json={"platform": platform, "token": token, "app_version": app_version})

    def delete(self, token: str) -> None:
        """On sign-out (best effort): a registration already gone (404) is not an error."""
        try:
            self._http.request("DELETE", f"/api/push/devices/{quote(token, safe='')}")
        except NotFoundError:
            pass
