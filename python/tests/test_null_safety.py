"""Null-safety regression tests for issue #2.

Mirrors ``NullSafetyTest.kt`` and ``NullSafetyTests.swift`` case-for-case.

The Python SDK uses ``dataclasses`` with hand-written ``from_dict`` methods
(not pydantic), so the nullability story is different — a present-but-null
on a ``d["key"]`` access silently coerces to ``None``, lying about the type,
and fails later as ``AttributeError: 'NoneType' object has no attribute '…'``
at the use site. The same fields are at risk as in the Kotlin/Swift SDKs.

Each test pairs a server response containing an explicit JSON ``null`` with
the expected decoded value (either the documented default or ``None``).
"""
from __future__ import annotations

import httpx
import pytest
import respx

from mechbase import Mechbase

BASE = "https://example.test"


@pytest.fixture
def client():
    c = Mechbase(token="tok", base_url=BASE)
    yield c
    c.close()


# --- A: defaulted text fields with explicit null fall back to "" -----------
# These mirror Swift's `(try? decode(...)) ?? ""` and Kotlin's
# `coerceInputValues = true` plus a Kotlin default.


@respx.mock
def test_user_full_name_null_falls_back_to_empty(client):
    respx.get(f"{BASE}/api/me/").mock(
        return_value=httpx.Response(
            200,
            json={
                "user": {"id": 1, "username": "u", "full_name": None, "email": "u@u"},
                "installations": [{"installation_id": 2012, "name": "Plant"}],
                "current_installation_id": 2012,
            },
        )
    )
    me = client.me()
    assert me.user.full_name == ""


@respx.mock
def test_route_description_null_falls_back_to_empty(client):
    """Was the exact production crash on installations 2012/2013
    (issue #164 server side; #2 client side)."""
    respx.get(f"{BASE}/api/installations/2012/routes").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{"uuid": "r-1", "name": "Daily", "description": None}],
                "total": 1,
                "limit": 50,
                "offset": 0,
            },
        )
    )
    routes = client.for_installation(2012).routes.list()
    assert len(routes) == 1
    assert routes[0].description == ""


@respx.mock
def test_item_response_notes_null_falls_back_to_empty(client):
    respx.post(f"{BASE}/api/installations/2012/routes/r-uuid/executions").mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "exec-1",
                "route_uuid": "r-uuid",
                "status": "in_progress",
                "started_at": "t",
                "completed_at": None,
                "session_id": "sess-1",
            },
        )
    )
    respx.post(f"{BASE}/api/installations/2012/executions/exec-1/responses").mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "resp-1",
                "route_item_uuid": "item-1",
                "data": {},
                "notes": None,
                "status": 1,
                "created_at": "t",
            },
        )
    )
    exec_handle = client.for_installation(2012).routes.start("r-uuid")
    resp = exec_handle.respond(route_item_uuid="item-1", data={"passed": True})
    assert resp.notes == ""


@respx.mock
def test_measurement_notes_null_falls_back_to_empty(client):
    respx.post(f"{BASE}/api/installations/2012/measurements/").mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "m-1",
                "measurement_point_id": 1,
                "point_sequence": 1,
                "data": {},
                "status": "good",
                "notes": None,
                "created_at": "t",
                "file_url": None,
            },
        )
    )
    m = client.for_installation(2012).measurements.create(
        point_id=1, data={"rms": 2.3}
    )
    assert m.notes == ""


# --- B: no-default fields widened to T | None ------------------------------


@respx.mock
def test_measurement_point_sequence_null_decodes_to_none(client):
    """`point_sequence` is genuinely DB-nullable on the server
    (`Measurement.point_sequence: null=True`); legacy/imported rows can be
    null. Mirror the Kotlin/Swift widening: type widens to `int | None` and
    the decoder uses `d.get(...)` (no default)."""
    respx.post(f"{BASE}/api/installations/2012/measurements/").mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "m-1",
                "measurement_point_id": 1,
                "point_sequence": None,
                "data": {"rms": 2.3},
                "status": "good",
                "notes": "",
                "created_at": "t",
                "file_url": None,
            },
        )
    )
    m = client.for_installation(2012).measurements.create(
        point_id=1, data={"rms": 2.3}
    )
    assert m.point_sequence is None
    assert m.status == "good"


# --- B (lockstep with Kotlin/Swift): MeasurementPoint optional metadata ----
# Backing columns are `blank=True, default=""` NOT NULL by intent, but they're
# optional metadata drift-plausible from a legacy import. Mirror the Kotlin
# `coerceInputValues = true` plus a Kotlin default, and the Swift
# `(try? decode(...)) ?? ""` pattern.


@respx.mock
def test_measurement_point_optional_metadata_all_null_decodes_to_empty(client):
    respx.post(f"{BASE}/api/installations/2012/measurement-points").mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "p-1",
                "point_id": 1,
                "name": "Drive End",
                "asset_id": 100,
                "transducer_type": None,
                "measurement_unit_code": None,
                "location": None,
                "status": 1,
                "external_id": "P-1-DE",
                "instructions": None,
            },
        )
    )
    p = client.for_installation(2012).measurement_points.create(
        name="Drive End", external_id="P-1-DE"
    )
    assert p.transducer_type == ""
    assert p.measurement_unit_code == ""
    assert p.location == ""
    assert p.instructions == ""


@respx.mock
def test_measurement_point_instructions_decodes(client):
    respx.post(f"{BASE}/api/installations/2012/measurement-points").mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "p-2",
                "point_id": 2,
                "name": "Drive End",
                "asset_id": 100,
                "transducer_type": "VB",
                "measurement_unit_code": "mm/s",
                "location": "",
                "status": 1,
                "external_id": None,
                "instructions": "<ul><li>Mount on the bearing housing.</li></ul>",
            },
        )
    )
    p = client.for_installation(2012).measurement_points.create(name="Drive End")
    assert p.instructions == "<ul><li>Mount on the bearing housing.</li></ul>"


# --- Regression guard: fully populated response still decodes the same -----


@respx.mock
def test_fully_populated_response_still_decodes(client):
    respx.post(f"{BASE}/api/installations/2012/measurements/").mock(
        return_value=httpx.Response(
            201,
            json={
                "uuid": "m-1",
                "measurement_point_id": 1,
                "point_sequence": 7,
                "data": {"rms": 2.3},
                "status": "good",
                "notes": "manual",
                "created_at": "t",
                "file_url": None,
            },
        )
    )
    m = client.for_installation(2012).measurements.create(
        point_id=1, data={"rms": 2.3}
    )
    assert m.point_sequence == 7
    assert m.notes == "manual"
