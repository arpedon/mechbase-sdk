"""Offline tests for registry CRUD, batch, files, history, errors."""
from __future__ import annotations

import httpx
import pytest
import respx

from mechbase import ConflictError, Mechbase, PayloadTooLargeError

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
