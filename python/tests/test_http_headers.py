"""X-Timezone on every request, and the conditional GET (ETag / If-None-Match / 304)."""
from __future__ import annotations

import httpx
import pytest
import respx

from mechbase import MechbaseError
from mechbase._http import HttpClient, local_timezone

BASE = "https://example.test"


@respx.mock
def test_x_timezone_explicit_default_and_off(monkeypatch):
    route = respx.get(f"{BASE}/x").mock(return_value=httpx.Response(200, json={}))
    HttpClient(token="t", base_url=BASE, timezone="Europe/Athens").request("GET", "/x")
    assert route.calls.last.request.headers["X-Timezone"] == "Europe/Athens"

    monkeypatch.setenv("TZ", "America/Chicago")
    HttpClient(token="t", base_url=BASE).request("GET", "/x")
    assert route.calls.last.request.headers["X-Timezone"] == "America/Chicago"

    HttpClient(token="t", base_url=BASE, timezone="").request("GET", "/x")
    assert "X-Timezone" not in route.calls.last.request.headers


def test_local_timezone_reads_tz_then_localtime(monkeypatch):
    monkeypatch.setenv("TZ", ":Asia/Tokyo")
    assert local_timezone() == "Asia/Tokyo"
    monkeypatch.setenv("TZ", "UTC0")  # a POSIX rule, not a zone name: fall through to /etc/localtime
    monkeypatch.setattr("os.path.realpath", lambda p: "/usr/share/zoneinfo/Europe/Athens")
    assert local_timezone() == "Europe/Athens"
    monkeypatch.setattr("os.path.realpath", lambda p: "/etc/localtime")
    assert local_timezone() is None


@respx.mock
def test_conditional_get_round_trip():
    route = respx.get(f"{BASE}/board").mock(side_effect=[
        httpx.Response(200, json={"name": "A"}, headers={"ETag": 'W/"v1"'}),
        httpx.Response(304),
        httpx.Response(200, json={"name": "B"}, headers={"ETag": 'W/"v2"'}),
    ])
    http = HttpClient(token="t", base_url=BASE, timezone="")
    body, etag = http.conditional("/board")
    assert body == {"name": "A"} and etag == 'W/"v1"'
    assert "If-None-Match" not in route.calls.last.request.headers
    assert http.conditional("/board", etag=etag) == (None, 'W/"v1"')
    assert route.calls.last.request.headers["If-None-Match"] == 'W/"v1"'  # echoed verbatim, weak prefix kept
    assert http.conditional("/board", etag=etag) == ({"name": "B"}, 'W/"v2"')


@respx.mock
def test_conditional_get_errors_raise():
    respx.get(f"{BASE}/board").mock(return_value=httpx.Response(404, json={"detail": "Not found."}))
    with pytest.raises(MechbaseError) as e:
        HttpClient(token="t", base_url=BASE).conditional("/board", etag='"x"')
    assert e.value.status == 404
