from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO

from ..models import FileAttachment, ItemResponse, Route, RouteExecution
from ._base import InstallationScoped, _clean, _paginated, _upload


def _key(idempotency_key: str | None) -> dict | None:
    return {"X-Idempotency-Key": idempotency_key} if idempotency_key else None


def _open_all(paths) -> tuple[list, list]:
    """(files tuples, the handles we opened) for a list of paths or open files."""
    out, opened = [], []
    for p in paths:
        if isinstance(p, (str, Path)):
            fh = open(p, "rb")  # noqa: SIM115
            opened.append(fh)
            out.append((Path(p).name, fh))
        else:
            out.append((Path(getattr(p, "name", "photo")).name, p))
    return out, opened


class Executions(InstallationScoped):
    """Operations on an existing execution."""

    def __init__(self, http, installation_id: int, execution_uuid: str):
        super().__init__(http, installation_id)
        self.uuid = execution_uuid

    def _url(self, suffix: str) -> str:
        return self._path(f"/executions/{self.uuid}{suffix}")

    def respond(
        self,
        *,
        route_item_uuid: str,
        data: dict,
        notes: str = "",
        photos: list[str | Path | BinaryIO] | None = None,
        idempotency_key: str | None = None,
    ) -> ItemResponse:
        payload: dict[str, Any] = {
            "route_item_uuid": route_item_uuid,
            "data": data,
            "notes": notes,
        }
        headers = {"X-Idempotency-Key": idempotency_key} if idempotency_key else None
        if not photos:
            body = self._http.request(
                "POST", self._url("/responses"), json=payload, headers=headers
            )
            return ItemResponse.from_dict(body)

        files = []
        opened = []
        try:
            for p in photos:
                if isinstance(p, (str, Path)):
                    fh = open(p, "rb")  # noqa: SIM115
                    opened.append(fh)
                    files.append(("files", (Path(p).name, fh)))
                else:
                    files.append(("files", (getattr(p, "name", "photo"), p)))
            body = self._http.request(
                "POST",
                self._url("/responses/upload"),
                data={"payload": json.dumps(payload)},
                files=files,
                headers=headers,
            )
        finally:
            for fh in opened:
                fh.close()
        return ItemResponse.from_dict(body)

    def add_field_item(
        self,
        *,
        label: str,
        item_type: str = "pass_fail",
        data: dict | None = None,
        zone_id: int | None = None,
        config: dict | None = None,
        notes: str = "",
    ) -> ItemResponse:
        """Append a new checklist item to this execution, field-authored.

        The item is zone-anchored (``zone_id``) or route-level (``None``).
        Asset assignment happens afterward via :meth:`triage`.
        """
        payload = {
            "label": label,
            "item_type": item_type,
            "data": data or {},
            "zone_id": zone_id,
            "config": config or {},
            "notes": notes,
        }
        body = self._http.request("POST", self._url("/items"), json=payload)
        return ItemResponse.from_dict(body)

    def triage(self, *, route_item_uuid: str, asset_id: int) -> ItemResponse:
        body = self._http.request(
            "POST",
            self._url("/triage"),
            json={"route_item_uuid": route_item_uuid, "asset_id": asset_id},
        )
        return ItemResponse.from_dict(body)

    def complete(self) -> RouteExecution:
        body = self._http.request("POST", self._url("/complete"))
        return RouteExecution.from_dict(body)

    def get(self) -> RouteExecution:
        return RouteExecution.from_dict(self._http.request("GET", self._url("")))

    def cancel(self) -> RouteExecution:
        """Abandon an execution that has no answers yet (409 once it has)."""
        return RouteExecution.from_dict(self._http.request("POST", self._url("/cancel")))

    def report(self) -> dict:
        """The run's report: {execution, route, can_amend, totals{checks, answered, passed, non_conformities},
        groups[{zone_id, label, entries[{check, response}]}], missing[check], exceptions[…]}."""
        return self._http.request("GET", self._url("/report"))

    # Amending a completed run (staff or whoever ran it; see report()["can_amend"]).

    def amend_answer(self, item_uuid: str, data: dict, *, notes: str = "",
                     idempotency_key: str | None = None) -> ItemResponse:
        """Answer a check the run missed. Send an `idempotency_key` so a retry returns the same answer."""
        return ItemResponse.from_dict(self._http.request(
            "POST", self._url(f"/amend/{item_uuid}/answer"), json={"data": data, "notes": notes},
            headers=_key(idempotency_key)))

    def amend_notes(self, item_uuid: str, notes: str) -> ItemResponse:
        return ItemResponse.from_dict(self._http.request("PATCH", self._url(f"/amend/{item_uuid}/notes"),
                                                         json={"notes": notes}))

    def amend_add_photo(self, item_uuid: str, file, *, filename: str = "photo.jpg",
                        uuid: str | None = None) -> FileAttachment:
        """A client `uuid` makes retries safe."""
        return FileAttachment.from_dict(_upload(self._http, self._url(f"/amend/{item_uuid}/photos"), file, filename,
                                                _clean({"uuid": uuid}) or None))

    def amend_remove_photo(self, item_uuid: str, file_uuid: str) -> None:
        self._http.request("DELETE", self._url(f"/amend/{item_uuid}/photos/{file_uuid}"))

    def amend_reading(self, item_uuid: str, *, value: float | None = None, comment: str = "",
                      images: list[str | Path | BinaryIO] | None = None,
                      data_file: str | Path | BinaryIO | None = None,
                      idempotency_key: str | None = None) -> ItemResponse:
        """Record a measurement check's missed reading (a value, or a data file and/or images)."""
        files, opened = _open_all(images or [])
        parts = [("images", f) for f in files]
        if data_file is not None:
            df, more = _open_all([data_file])
            opened += more
            parts.append(("data_file", df[0]))
        form = _clean({"value": value, "comment": comment})
        try:
            body = self._http.request("POST", self._url(f"/amend/{item_uuid}/reading"), data=form,
                                      files=parts or None, headers=_key(idempotency_key))
        finally:
            for fh in opened:
                fh.close()
        return ItemResponse.from_dict(body)


class Routes(InstallationScoped):
    def list(self, *, q: str = "", limit: int = 50, offset: int = 0) -> list[Route]:
        return _paginated(
            self._http,
            self._path("/routes"),
            params={"q": q, "limit": limit, "offset": offset},
            parse=Route.from_dict,
        )

    def get(self, route_uuid: str) -> dict:
        return self._http.request("GET", self._path(f"/routes/{route_uuid}"))

    def start(self, route_uuid: str) -> Executions:
        body = self._http.request(
            "POST", self._path(f"/routes/{route_uuid}/executions")
        )
        execution = RouteExecution.from_dict(body)
        handle = Executions(self._http, self._iid, execution.uuid)
        handle.execution = execution  # type: ignore[attr-defined]
        return handle

    def execution(self, execution_uuid: str) -> Executions:
        return Executions(self._http, self._iid, execution_uuid)

    def create(self, name: str, items: list[dict], *, description: str = "", uuid: str | None = None) -> dict:
        """A route with at least one check, in reading order. Each item: label, item_type
        (pass_fail|numerical|multi_check|measurement), instructions, unit, subchecks, asset_id, zone_id,
        measurement_point_id, uuid. Client-minted uuids (route and items) make a retry return the route."""
        return self._http.request("POST", self._path("/routes"),
                                  json=_clean({"uuid": uuid, "name": name, "description": description,
                                               "items": list(items)}))

    def update(self, route_uuid: str, *, name: str | None = None, description: str | None = None) -> Route:
        return Route.from_dict(self._http.request("PATCH", self._path(f"/routes/{route_uuid}"),
                                                  json=_clean({"name": name, "description": description})))

    def delete(self, route_uuid: str) -> None:
        """Deletes the route and its runs; 409 while a run is open, and for an asset's checklist route."""
        self._http.request("DELETE", self._path(f"/routes/{route_uuid}"))

    def executions(self, route_uuid: str, *, limit: int = 50, offset: int = 0) -> dict:
        """Run history, newest first: {items[{uuid, number, status, started_at, completed_at, executed_by,
        answered_count, passed_count, non_conformity_count, max_status}], total, limit, offset}."""
        return self._http.request("GET", self._path(f"/routes/{route_uuid}/executions"),
                                  params={"limit": limit, "offset": offset})

    def add_item(self, route_uuid: str, label: str, *, item_type: str = "pass_fail", uuid: str | None = None,
                 **fields) -> dict:
        """Append a check (fields as in create()). A client `uuid` makes a retry return the check."""
        body = _clean({"uuid": uuid, "label": label, "item_type": item_type, **fields})
        return self._http.request("POST", self._path(f"/routes/{route_uuid}/items"), json=body)

    def update_item(self, route_uuid: str, item_uuid: str, **fields) -> dict:
        """label, item_type, instructions, unit, subchecks; unsent fields keep their value."""
        return self._http.request("PATCH", self._path(f"/routes/{route_uuid}/items/{item_uuid}"), json=fields)

    def delete_item(self, route_uuid: str, item_uuid: str) -> None:
        """A check past runs answered is archived instead, so their reports keep it."""
        self._http.request("DELETE", self._path(f"/routes/{route_uuid}/items/{item_uuid}"))

    def reorder_items(self, route_uuid: str, items: list[dict]) -> list[dict]:
        """[{uuid, position, zone_id?, asset_id?}]: position within its stop; zone_id/asset_id move it
        (None clears, omitted keeps). Returns the renumbered [{uuid, check_id}]."""
        return self._http.request("POST", self._path(f"/routes/{route_uuid}/items/reorder"),
                                  json={"items": list(items)})["items"]

    def set_item_photo(self, route_uuid: str, item_uuid: str, file, *, filename: str = "photo.jpg",
                       uuid: str | None = None) -> FileAttachment:
        """The check's reference photo (replaces the old one). A client `uuid` makes retries safe; a late
        retry of a replaced photo is a 409 (keep the newer)."""
        return FileAttachment.from_dict(_upload(self._http, self._path(f"/routes/{route_uuid}/items/{item_uuid}/photos"),
                                                file, filename, _clean({"uuid": uuid}) or None))

    def item_history(self, route_uuid: str, item_uuid: str, *, limit: int = 50, offset: int = 0) -> dict:
        """A check's answers across runs, newest first: {items[{response_uuid, execution_uuid, executed_by,
        status, data, notes, point_sequence, …}], total, limit, offset}."""
        return self._http.request("GET", self._path(f"/routes/{route_uuid}/items/{item_uuid}/history"),
                                  params={"limit": limit, "offset": offset})

    def set_response_notes(self, response_uuid: str, notes: str) -> ItemResponse:
        """Edit any response's notes (the report's notes editor)."""
        return ItemResponse.from_dict(self._http.request("PATCH", self._path(f"/responses/{response_uuid}"),
                                                         json={"notes": notes}))

    def start_survey(self, name: str = "", *, uuid: str | None = None) -> Executions:
        """A blank route and its first run; add checks during the walk (execution.add_field_item).
        A client `uuid` (the run's) makes retries safe. The handle carries .route and .execution."""
        body = self._http.request("POST", self._path("/surveys"), json=_clean({"name": name, "uuid": uuid}))
        handle = Executions(self._http, self._iid, body["execution"]["uuid"])
        handle.execution = RouteExecution.from_dict(body["execution"])  # type: ignore[attr-defined]
        handle.route = body["route"]  # type: ignore[attr-defined]
        return handle


class NonConformities(InstallationScoped):
    """Failed checks across runs, to follow up and resolve."""

    def list(self, *, status: str = "open", asset_id: int | None = None, limit: int = 50, offset: int = 0) -> dict:
        """status open|resolved|all. {items[{response_uuid, route_name, label, asset_id, status, notes,
        created_at, resolved_at, resolved_by, resolution_comment, …}], total, limit, offset}."""
        return self._http.request("GET", self._path("/non-conformities"),
                                  params=_clean({"status": status, "asset_id": asset_id, "limit": limit,
                                                 "offset": offset}))

    def resolve(self, response_uuid: str, *, comment: str = "") -> dict:
        """A retry by whoever resolved it returns it again; resolved by someone else is a 409."""
        return self._http.request("POST", self._path(f"/non-conformities/{response_uuid}/resolve"),
                                  json={"comment": comment})
