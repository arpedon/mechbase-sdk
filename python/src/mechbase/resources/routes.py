from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO

from ..models import ItemResponse, Route, RouteExecution
from ._base import InstallationScoped, _paginated


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
