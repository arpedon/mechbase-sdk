from __future__ import annotations

from typing import Any

import httpx

from .errors import (
    AuthError,
    ConflictError,
    MechbaseError,
    NotFoundError,
    PayloadTooLargeError,
    ValidationError,
)


class HttpClient:
    def __init__(self, *, token: str | None, base_url: str, timeout: float = 30.0):
        headers = {
            "User-Agent": "mechbase-python/0.2",
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any = None,
        data: dict | None = None,
        files: dict | list | None = None,
        headers: dict | None = None,
    ) -> Any:
        response = self._client.request(
            method,
            path,
            params=params,
            json=json,
            data=data,
            files=files,
            headers=headers,
        )
        return self._handle(response)

    @staticmethod
    def _handle(response: httpx.Response) -> Any:
        if response.status_code == 204:
            return None
        try:
            body = response.json()
        except Exception:
            body = response.text

        if 200 <= response.status_code < 300:
            return body

        detail = body.get("detail") if isinstance(body, dict) else str(body)
        message = f"{response.status_code} {detail}"
        if response.status_code in (401, 403):
            raise AuthError(message, status=response.status_code, body=body)
        if response.status_code == 404:
            raise NotFoundError(message, status=response.status_code, body=body)
        if response.status_code == 422:
            raise ValidationError(message, status=response.status_code, body=body)
        if response.status_code == 409:
            raise ConflictError(message, status=response.status_code, body=body)
        if response.status_code == 413:
            raise PayloadTooLargeError(message, status=response.status_code, body=body)
        raise MechbaseError(message, status=response.status_code, body=body)
