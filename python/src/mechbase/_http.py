from __future__ import annotations

import math
import time
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

MAX_RETRIES = 5
# The API allows 60 requests a minute: a 429 asks for up to ~60 s, so a bulk job waits it out;
# a longer wait (the hourly window) fails fast with the server's message.
MAX_WAIT = 60.0


def _retry_after(response: httpx.Response) -> float | None:
    try:
        wait = float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None
    return max(0.0, wait) if math.isfinite(wait) else None


def _seekable(f) -> bool:
    try:
        return bool(f.seekable())
    except Exception:
        return False


def _streams(files) -> list:
    """File-like objects in a httpx `files` arg (a retry must rewind them)."""
    items = files.values() if isinstance(files, dict) else [v for _, v in files or []]
    out = []
    for v in items:
        v = v[1] if isinstance(v, tuple) else v
        if hasattr(v, "read"):
            out.append(v)
    return out


class HttpClient:
    def __init__(self, *, token: str | None, base_url: str, timeout: float = 30.0, sleep=time.sleep,
                 max_retries: int = MAX_RETRIES):
        """max_retries: how many times a 429 is retried (0 turns retrying off)."""
        self._sleep = sleep
        self._max_retries = max(0, max_retries)
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
        raw: bool = False,
    ) -> Any:
        streams = _streams(files)
        starts = [f.tell() for f in streams if _seekable(f)]
        retryable = len(starts) == len(streams)
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            response = self._client.request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                files=files,
                headers=headers,
            )
            if response.status_code != 429 or not retryable or attempt == attempts - 1:
                break
            # The server throttles before doing any work, so a retry is safe for every method.
            wait = _retry_after(response)
            if wait is None:
                wait = 2.0**attempt
            if wait > MAX_WAIT:
                # Fail fast rather than stall for minutes; the error's retry_after lets the caller wait.
                return self._handle(
                    response, note=f" (the server asked to wait {wait:g} s, over the {MAX_WAIT:g} s retry cap)"
                )
            self._sleep(wait)
            for f, pos in zip(streams, starts):
                f.seek(pos)
        if raw and 200 <= response.status_code < 300:
            return response.content
        return self._handle(response)

    @staticmethod
    def _handle(response: httpx.Response, note: str = "") -> Any:
        if response.status_code == 204:
            return None
        try:
            body = response.json()
        except Exception:
            body = response.text

        if 200 <= response.status_code < 300:
            return body

        detail = body.get("detail") if isinstance(body, dict) else str(body)
        message = f"{response.status_code} {detail}{note}"
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
        retry_after = _retry_after(response) if response.status_code == 429 else None
        raise MechbaseError(message, status=response.status_code, body=body, retry_after=retry_after)
