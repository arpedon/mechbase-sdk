from __future__ import annotations

import httpx
import respx

from mechbase import Mechbase

BASE = "https://example.test"

_MEAS = {
    "uuid": "m1", "measurement_point_id": 5, "point_sequence": 1,
    "data": {"rms": 1.2}, "status": "good", "notes": "",
    "created_at": "2026-01-01T00:00:00Z", "file_url": None,
}
_RESP = {
    "uuid": "r1", "route_item_uuid": "item-1", "data": {"passed": True},
    "notes": "", "status": 1, "created_at": "2026-01-01T00:00:01Z",
}


@respx.mock
def test_create_sends_idempotency_header():
    route = respx.post(f"{BASE}/api/installations/2012/measurements/").mock(
        return_value=httpx.Response(201, json=_MEAS)
    )
    Mechbase(token="t", base_url=BASE).for_installation(2012).measurements.create(
        point_id=5, data={"rms": 1.2}, idempotency_key="k"
    )
    assert route.calls.last.request.headers.get("X-Idempotency-Key") == "k"


@respx.mock
def test_create_without_key_sends_no_header():
    route = respx.post(f"{BASE}/api/installations/2012/measurements/").mock(
        return_value=httpx.Response(201, json=_MEAS)
    )
    Mechbase(token="t", base_url=BASE).for_installation(2012).measurements.create(
        point_id=5, data={"rms": 1.2}
    )
    assert route.calls.last.request.headers.get("X-Idempotency-Key") is None


@respx.mock
def test_respond_sends_idempotency_header():
    route = respx.post(
        f"{BASE}/api/installations/2012/executions/exec-1/responses"
    ).mock(return_value=httpx.Response(201, json=_RESP))
    Mechbase(token="t", base_url=BASE).for_installation(2012).routes.execution(
        "exec-1"
    ).respond(route_item_uuid="item-1", data={"passed": True}, idempotency_key="k")
    assert route.calls.last.request.headers.get("X-Idempotency-Key") == "k"
