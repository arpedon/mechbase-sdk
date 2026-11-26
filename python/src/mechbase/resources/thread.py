from __future__ import annotations

from ._base import InstallationScoped, _clean, _upload


def _refs(references: list[dict] | None) -> list[dict]:
    """[{"point_id": 2, "point_sequence": 766}, …]; point_sequence is optional."""
    return [_clean(r) for r in references or []]


class Comments(InstallationScoped):
    """The asset thread. Bodies are HTML; `body_text` on each comment is the plain text."""

    def list(self, asset_id: int, *, limit: int = 50, offset: int = 0) -> list[dict]:
        """Newest first. Each: id, body, body_text, author_name, created_at, edited_at,
        references, is_finding, editable (by you)."""
        return self._http.request("GET", self._path(f"/assets/{asset_id}/comments"),
                                  params={"limit": limit, "offset": offset})["items"]

    def create(self, asset_id: int, body: str, *, references: list[dict] | None = None) -> dict:
        return self._http.request("POST", self._path(f"/assets/{asset_id}/comments"),
                                  json={"body": body, "references": _refs(references)})

    def update(self, asset_id: int, comment_id: int, body: str, *, references: list[dict] | None = None) -> dict:
        """Replace the body and the whole reference set. Only the author may."""
        return self._http.request("PATCH", self._path(f"/assets/{asset_id}/comments/{comment_id}"),
                                  json={"body": body, "references": _refs(references)})

    def delete(self, asset_id: int, comment_id: int) -> None:
        """Only the author may; a finding's note cannot be deleted."""
        self._http.request("DELETE", self._path(f"/assets/{asset_id}/comments/{comment_id}"))


class Documents(InstallationScoped):
    """An asset's documents (photos are on assets.add_photo)."""

    KINDS = ("attachment", "drawing", "datasheet", "manual", "check_sheet", "test_report")

    def list(self, asset_id: int) -> list[dict]:
        """Newest first. Each: uuid, name, kind, url, created_at."""
        return self._http.request("GET", self._path(f"/assets/{asset_id}/documents"))

    def add(self, asset_id: int, file, *, filename: str = "document.pdf", kind: str = "attachment",
            uuid: str | None = None) -> dict:
        """Upload one document. A client `uuid` makes retries safe."""
        return _upload(self._http, self._path(f"/assets/{asset_id}/documents"), file, filename,
                       _clean({"kind": kind, "uuid": uuid}))

    def delete(self, asset_id: int, document_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/assets/{asset_id}/documents/{document_uuid}"))


class AlarmRules(InstallationScoped):
    """A point's alarm rules: its own overrides, then the installation defaults.
    Only threshold overrides can be written; defaults are read-only."""

    def list(self, point_id: int) -> list[dict]:
        """Each: uuid, scope (point|installation), method, data_key, effective_data_key,
        direction, minor_threshold, major_threshold, threshold_mode, source."""
        return self._http.request("GET", self._path(f"/measurement-points/{point_id}/alarm-rules"))

    def create(self, point_id: int, *, minor_threshold: float, major_threshold: float,
               data_key: str = "", direction: str = "high") -> dict:
        """The point's threshold override (409 if it already has one: update it)."""
        body = _clean({"method": "threshold", "data_key": data_key, "direction": direction,
                       "minor_threshold": minor_threshold, "major_threshold": major_threshold})
        return self._http.request("POST", self._path(f"/measurement-points/{point_id}/alarm-rules"), json=body)

    def update(self, point_id: int, rule_uuid: str, *, minor_threshold: float | None = None,
               major_threshold: float | None = None, data_key: str | None = None,
               direction: str | None = None) -> dict:
        """Change only the fields given."""
        body = _clean({"minor_threshold": minor_threshold, "major_threshold": major_threshold,
                       "data_key": data_key, "direction": direction})
        return self._http.request("PATCH", self._path(f"/measurement-points/{point_id}/alarm-rules/{rule_uuid}"),
                                  json=body)

    def delete(self, point_id: int, rule_uuid: str) -> None:
        """Remove the override; the point falls back to the installation default."""
        self._http.request("DELETE", self._path(f"/measurement-points/{point_id}/alarm-rules/{rule_uuid}"))
