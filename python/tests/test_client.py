"""Offline tests — use respx to mock the HTTP layer."""

from __future__ import annotations

import httpx
import pytest
import respx

from mechbase import AuthError, Mechbase


@pytest.fixture
def client():
    c = Mechbase(token="tok", base_url="https://example.test")
    yield c
    c.close()


@respx.mock
def test_me(client):
    respx.get("https://example.test/api/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "user": {"id": 1, "username": "u", "full_name": "U U", "email": "u@u"},
                "installations": [{"installation_id": 2012, "name": "Plant"}],
                "current_installation_id": 2012,
            },
        )
    )
    me = client.me()
    assert me.user.username == "u"
    assert me.current_installation_id == 2012
    assert me.installations[0].name == "Plant"


@respx.mock
def test_list_assets(client):
    respx.get("https://example.test/api/installations/2012/assets").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "uuid": "00000000-0000-0000-0000-000000000001",
                        "asset_id": 1,
                        "name": "Pump 1",
                        "zone_id": 1,
                        "machine_class": "II",
                        "status": 1,
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            },
        )
    )
    assets = client.for_installation(2012).assets.list()
    assert len(assets) == 1
    assert assets[0].name == "Pump 1"


@respx.mock
def test_create_measurement(client):
    respx.post("https://example.test/api/installations/2012/measurements/").mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "00000000-0000-0000-0000-000000000002",
                "measurement_point_id": 1,
                "point_sequence": 5,
                "data": {"rms": 2.3},
                "status": "good",
                "notes": "",
                "created_at": "2026-04-08T10:00:00Z",
                "file_url": None,
            },
        )
    )
    m = client.for_installation(2012).measurements.create(point_id=1, data={"rms": 2.3})
    assert m.point_sequence == 5
    assert m.status == "good"


@respx.mock
def test_auth_error_raises(client):
    respx.get("https://example.test/api/me").mock(
        return_value=httpx.Response(401, json={"detail": "nope"})
    )
    with pytest.raises(AuthError):
        client.me()


@respx.mock
def test_start_execution_and_respond(client):
    respx.post(
        "https://example.test/api/installations/2012/routes/r-uuid/executions"
    ).mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "exec-uuid",
                "route_uuid": "r-uuid",
                "status": "in_progress",
                "started_at": "2026-04-08T10:00:00Z",
                "completed_at": None,
                "session_id": "sess-uuid",
            },
        )
    )
    respx.post(
        "https://example.test/api/installations/2012/executions/exec-uuid/responses"
    ).mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "resp-uuid",
                "route_item_uuid": "item-uuid",
                "data": {"passed": True},
                "notes": "",
                "status": 1,
                "created_at": "2026-04-08T10:00:01Z",
            },
        )
    )
    execution = client.for_installation(2012).routes.start("r-uuid")
    resp = execution.respond(route_item_uuid="item-uuid", data={"passed": True})
    assert resp.status == 1
