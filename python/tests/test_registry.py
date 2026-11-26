"""Offline tests for registry CRUD, batch, files, history, errors."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from mechbase import ConflictError, Mechbase, MechbaseError, PayloadTooLargeError

BASE = "https://example.test"


@pytest.fixture
def client():
    c = Mechbase(token="tok", base_url=BASE)
    yield c
    c.close()


@respx.mock
def test_conflict_error(client):
    respx.post(f"{BASE}/api/installations/2012/assets").mock(
        return_value=httpx.Response(409, json={"detail": "duplicate external_id"})
    )
    with pytest.raises(ConflictError):
        client.for_installation(2012).assets.create(name="Pump", external_id="P-1")


@respx.mock
def test_payload_too_large_error(client):
    respx.post(
        f"{BASE}/api/installations/2012/measurements/m-1/files/"
    ).mock(return_value=httpx.Response(413, json={"detail": "too big"}))
    with pytest.raises(PayloadTooLargeError):
        client.for_installation(2012).measurements.add_file("m-1", file=b"x")


@respx.mock
def test_asset_crud_roundtrip(client):
    respx.post(f"{BASE}/api/installations/2012/assets").mock(
        return_value=httpx.Response(201, json={
            "uuid": "a-1", "asset_id": 7, "name": "Pump 7", "section_id": 3,
            "zone_id": 2, "machine_class": "II", "equipment_type": "pump",
            "status": 1, "external_id": "P-7"})
    )
    respx.put(f"{BASE}/api/installations/2012/assets").mock(
        return_value=httpx.Response(200, json={
            "uuid": "a-1", "asset_id": 7, "name": "Pump 7b", "section_id": 3,
            "zone_id": 2, "machine_class": "II", "equipment_type": "pump",
            "status": 1, "external_id": "P-7"})
    )
    respx.patch(f"{BASE}/api/installations/2012/assets/7").mock(
        return_value=httpx.Response(200, json={
            "uuid": "a-1", "asset_id": 7, "name": "Pump 7c", "section_id": 3,
            "zone_id": 2, "machine_class": "II", "equipment_type": "pump",
            "status": 1, "external_id": "P-7"})
    )
    respx.delete(f"{BASE}/api/installations/2012/assets/7").mock(
        return_value=httpx.Response(200, json={"deleted": True, "uuid": "a-1"})
    )
    assets = client.for_installation(2012).assets
    created = assets.create(name="Pump 7", external_id="P-7", section_external_id="S-1")
    assert created.asset_id == 7 and created.equipment_type == "pump"
    upserted = assets.upsert(external_id="P-7", name="Pump 7b")
    assert upserted.name == "Pump 7b"
    updated = assets.update(7, name="Pump 7c")
    assert updated.name == "Pump 7c"
    patch_call = next(c for c in respx.calls if c.request.method == "PATCH")
    assert json.loads(patch_call.request.content) == {"name": "Pump 7c"}
    deleted = assets.delete(7, cascade=True)
    assert deleted.deleted is True and deleted.uuid == "a-1"


@respx.mock
def test_sections_and_zones(client):
    respx.get(f"{BASE}/api/installations/2012/sections").mock(
        return_value=httpx.Response(200, json={"items": [
            {"uuid": "s-1", "section_id": 3, "name": "Hall A", "external_id": "S-1"}],
            "total": 1, "limit": 50, "offset": 0})
    )
    respx.post(f"{BASE}/api/installations/2012/zones").mock(
        return_value=httpx.Response(201, json={
            "uuid": "z-1", "zone_id": 9, "name": "Zone 9",
            "section_id": 3, "external_id": "Z-9"})
    )
    inst = client.for_installation(2012)
    sections = inst.sections.list()
    assert sections[0].name == "Hall A" and sections[0].section_id == 3
    zone = inst.zones.create(name="Zone 9", external_id="Z-9", section_external_id="S-1")
    assert zone.zone_id == 9 and zone.section_id == 3


@respx.mock
def test_create_batch(client):
    respx.post(f"{BASE}/api/installations/2012/measurements/batch/").mock(
        return_value=httpx.Response(200, json={
            "created": 1, "duplicates": 1, "errors": 0,
            "results": [
                {"index": 0, "status": "created", "measurement_point_id": 1,
                 "point_sequence": 5, "uuid": "m-1", "external_id": "E-0", "detail": None},
                {"index": 1, "status": "duplicate", "measurement_point_id": 1,
                 "point_sequence": 5, "uuid": "m-1", "external_id": "E-1", "detail": None},
            ]})
    )
    res = client.for_installation(2012).measurements.create_batch([
        {"measurement_point_id": 1, "data": {"rms": 2.3}, "external_id": "E-0"},
        {"measurement_point_external_id": "PUMP-DE", "data": {"rms": 2.4}, "external_id": "E-1"},
    ])
    assert res.created == 1 and res.duplicates == 1
    assert res.results[0].status == "created"


@respx.mock
def test_add_file(client):
    respx.post(f"{BASE}/api/installations/2012/measurements/m-1/files/").mock(
        return_value=httpx.Response(201, json={
            "uuid": "f-1", "name": "spec.csv", "kind": "spectrum",
            "file_url": "https://cdn/x", "created_at": "2026-04-08T10:00:00Z"})
    )
    f = client.for_installation(2012).measurements.add_file("m-1", file=b"col\n1\n", filename="spec.csv")
    assert f.uuid == "f-1" and f.kind == "spectrum"


@respx.mock
def test_iter_for_point_cursor(client):
    route = respx.get(f"{BASE}/api/installations/2012/measurement-points/42/measurements/")
    route.side_effect = [
        httpx.Response(200, json={"items": [
            {"uuid": "m-1", "measurement_point_id": 42, "point_sequence": 1,
             "data": {}, "status": "good", "notes": "", "created_at": "t1"}],
            "next_cursor": "CUR2"}),
        httpx.Response(200, json={"items": [
            {"uuid": "m-2", "measurement_point_id": 42, "point_sequence": 2,
             "data": {}, "status": "good", "notes": "", "created_at": "t2"}],
            "next_cursor": None}),
    ]
    got = list(client.for_installation(2012).measurements.iter_for_point(42, page_size=1))
    assert [m.uuid for m in got] == ["m-1", "m-2"]
    assert respx.calls[1].request.url.params["cursor"] == "CUR2"


I = f"{BASE}/api/installations/2012"
ATYPE = {"uuid": "t-1", "code": "QB-STD", "name": "QB", "manufacturer": "ACME", "checklist": [{"title": "Oil"}],
         "external_id": None, "asset_count": 2, "document_count": 1}
ASSET = {"uuid": "a", "asset_id": 1, "name": "P", "status": 1, "asset_type": "QB-STD"}


@respx.mock
def test_asset_types_paths_verbs_bodies(client):
    at = client.for_installation(2012).asset_types
    respx.get(f"{I}/asset-types").mock(return_value=httpx.Response(200, json=[ATYPE]))
    respx.get(f"{I}/asset-types/QB-STD").mock(return_value=httpx.Response(200, json=ATYPE))
    put = respx.put(f"{I}/asset-types").mock(return_value=httpx.Response(200, json=ATYPE))
    patch = respx.patch(f"{I}/asset-types/QB-STD").mock(return_value=httpx.Response(200, json=ATYPE))
    respx.delete(f"{I}/asset-types/QB-STD").mock(return_value=httpx.Response(200, json={"deleted": True, "uuid": "t-1"}))
    docs = respx.get(f"{I}/asset-types/QB-STD/documents").mock(return_value=httpx.Response(200, json=[{"uuid": "d"}]))
    up = respx.post(f"{I}/asset-types/QB-STD/documents").mock(return_value=httpx.Response(201, json={"uuid": "d", "kind": "manual"}))
    rm = respx.delete(f"{I}/asset-types/QB-STD/documents/d").mock(return_value=httpx.Response(204))

    assert at.list()[0].asset_count == 2 and at.get("QB-STD").checklist == [{"title": "Oil"}]
    at.upsert("QB-STD", name="QB", checklist=[{"title": "Oil"}])
    assert json.loads(put.calls.last.request.content) == {"code": "QB-STD", "name": "QB", "checklist": [{"title": "Oil"}]}
    at.update("QB-STD", manufacturer="ACME")
    assert json.loads(patch.calls.last.request.content) == {"manufacturer": "ACME"}
    assert at.delete("QB-STD").deleted
    assert at.documents("QB-STD") == [{"uuid": "d"}]
    at.add_document("QB-STD", b"%PDF", kind="manual", uuid="d")
    body = up.calls.last.request.content
    assert b'name="kind"\r\n\r\nmanual' in body and b'name="uuid"\r\n\r\nd' in body
    assert at.delete_document("QB-STD", "d") is None and rm.called and docs.called


@respx.mock
def test_zone_guest_view_asset_type_omitted_vs_null_checklist(client):
    inst = client.for_installation(2012)
    z = respx.patch(f"{I}/zones/3").mock(return_value=httpx.Response(200, json={"uuid": "z", "zone_id": 3, "name": "Z", "guest_view": True}))
    a = respx.patch(f"{I}/assets/1").mock(return_value=httpx.Response(200, json=ASSET))
    cl = respx.post(f"{I}/assets/1/checklist").mock(return_value=httpx.Response(200, json={"route_uuid": "r", "created": True}))

    assert inst.zones.update(3, guest_view=True).guest_view is True
    assert json.loads(z.calls.last.request.content) == {"guest_view": True}
    assert inst.assets.update(1, name="P").asset_type == "QB-STD"
    assert json.loads(a.calls.last.request.content) == {"name": "P"}
    inst.assets.update(1, asset_type=None)
    assert json.loads(a.calls.last.request.content) == {"asset_type": None}
    inst.assets.update(1, asset_type="QB-STD")
    assert json.loads(a.calls.last.request.content) == {"asset_type": "QB-STD"}
    assert inst.assets.ensure_checklist(1) == {"route_uuid": "r", "created": True} and cl.called


@respx.mock
def test_429_retry_after_header():
    waits = []
    c = Mechbase(token="tok", base_url=BASE)
    c._http._sleep = waits.append
    route = respx.get(f"{BASE}/api/me/").mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "2"}, json={"detail": "Too many requests."}),
        httpx.Response(200, json={"ok": 1}),
    ])
    c._http.request("GET", "/api/me/")
    assert route.call_count == 2 and waits == [2.0]


@respx.mock
def test_429_backoff_then_gives_up():
    waits = []
    c = Mechbase(token="tok", base_url=BASE)
    c._http._sleep = waits.append
    route = respx.get(f"{BASE}/api/me/").mock(return_value=httpx.Response(429, json={"detail": "Too many requests."}))
    with pytest.raises(MechbaseError) as e:
        c._http.request("GET", "/api/me/")
    assert e.value.status == 429 and route.call_count == 6
    assert waits == [1.0, 2.0, 4.0, 8.0, 16.0]


@respx.mock
def test_429_wait_capped():
    waits = []
    c = Mechbase(token="tok", base_url=BASE)
    c._http._sleep = waits.append
    respx.get(f"{BASE}/api/me/").mock(side_effect=[
        httpx.Response(429, headers={"Retry-After": "120"}), httpx.Response(200, json={"ok": 1})])
    c._http.request("GET", "/api/me/")
    assert waits == [30.0]


@respx.mock
def test_set_guest_view_bodies(client):
    route = respx.post(f"{BASE}/api/installations/7/zones/guest-view").mock(
        return_value=httpx.Response(200, json={"updated": 3}))
    zones = client.for_installation(7).zones
    assert zones.set_guest_view(True) == 3
    assert json.loads(route.calls.last.request.content) == {"enabled": True}
    zones.set_guest_view(False, zone_ids=[1, 2])
    assert json.loads(route.calls.last.request.content) == {"enabled": False, "zone_ids": [1, 2]}
    zones.set_guest_view(True, section_id=9)
    assert json.loads(route.calls.last.request.content) == {"enabled": True, "section_id": 9}


@respx.mock
def test_asset_type_on_create_and_upsert(client):
    a = {"uuid": "x", "asset_id": 5, "name": "P", "status": 1}
    post = respx.post(f"{BASE}/api/installations/7/assets").mock(return_value=httpx.Response(200, json=a))
    put = respx.put(f"{BASE}/api/installations/7/assets").mock(return_value=httpx.Response(200, json=a))
    assets = client.for_installation(7).assets
    assets.create(name="P", asset_type="QB")
    assets.upsert(name="P", external_id="e", asset_type="QB")
    assert json.loads(post.calls.last.request.content) == {"name": "P", "asset_type": "QB"}
    assert json.loads(put.calls.last.request.content)["asset_type"] == "QB"
    assets.create(name="P")
    assert "asset_type" not in json.loads(post.calls.last.request.content)
