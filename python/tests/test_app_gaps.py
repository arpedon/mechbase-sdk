"""The gaps the app lanes found: reading get/delete, error detail, finding → reading, retry-safe comments,
asset activity, inherited documents, asset production state."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from mechbase import ConflictError, Mechbase, MechbaseError, NotFoundError, ValidationError

BASE = "https://example.test"
I = f"{BASE}/api/installations/7"
READING = f"{I}/measurement-points/2/measurements/766/"


@pytest.fixture
def inst():
    c = Mechbase(token="tok", base_url=BASE)
    yield c.for_installation(7)
    c.close()


@respx.mock
def test_reading_get_and_delete(inst):
    respx.get(READING).mock(return_value=httpx.Response(200, json={
        "uuid": "m", "measurement_point_id": 2, "point_sequence": 766, "data": {}, "status": "good", "notes": "",
        "created_at": "2026-11-27T10:00:00Z"}))
    assert inst.measurements.get(2, 766).point_sequence == 766
    respx.delete(READING).mock(return_value=httpx.Response(200, json={"deleted": True, "uuid": "m"}))
    assert inst.measurements.delete(2, 766).deleted is True
    respx.get(f"{I}/measurement-points/2/measurements/1/").mock(return_value=httpx.Response(404, json={"detail": "x"}))
    with pytest.raises(NotFoundError):
        inst.measurements.get(2, 1)


@respx.mock
def test_error_detail_drops_the_status(inst):
    respx.post(f"{I}/assets/1/comments").mock(return_value=httpx.Response(
        409, json={"detail": "That uuid belongs to another comment."}))
    with pytest.raises(ConflictError) as e:
        inst.comments.create(1, "b", uuid="u")
    assert str(e.value).startswith("409 ") and e.value.detail == "That uuid belongs to another comment."
    assert ValidationError("422 bad", status=422, body="bad").detail == "bad"
    assert MechbaseError("plain").detail == "plain"


@respx.mock
def test_finding_links_to_its_reading(inst):
    row = {"uuid": "f", "status": "open", "created_at": "t", "point_sequence": 766}
    respx.get(f"{I}/findings/f/").mock(side_effect=[httpx.Response(200, json=row),
                                                   httpx.Response(200, json={**row, "point_sequence": None})])
    f = inst.findings.get("f")
    assert f.point_sequence == 766 and "point_sequence" not in f.extra
    assert inst.findings.get("f").point_sequence is None


@respx.mock
def test_comment_create_sends_client_uuid_only_when_given(inst):
    route = respx.post(f"{I}/assets/1/comments").mock(return_value=httpx.Response(201, json={"id": 5, "uuid": "u"}))
    assert inst.comments.create(1, "b", uuid="u")["uuid"] == "u"
    assert json.loads(route.calls.last.request.content) == {"body": "b", "references": [], "uuid": "u"}
    inst.comments.create(1, "b")
    assert json.loads(route.calls.last.request.content) == {"body": "b", "references": []}


@respx.mock
def test_activity_by_asset(inst):
    route = respx.get(f"{I}/activity").mock(return_value=httpx.Response(200, json={"items": [], "next_cursor": None}))
    assert list(inst.activity.iter(asset_id=4)) == []
    assert route.calls.last.request.url.params["asset_id"] == "4"


@respx.mock
def test_documents_inherited_and_asset_production_state(inst):
    respx.get(f"{I}/assets/1/documents").mock(return_value=httpx.Response(200, json=[
        {"uuid": "a", "inherited": False}, {"uuid": "b", "inherited": True}]))
    assert [d["inherited"] for d in inst.documents.list(1)] == [False, True]
    asset = {"uuid": "x", "asset_id": 1, "name": "P", "section_id": 1, "zone_id": None, "status": 1,
             "running": "on", "running_since": "2026-11-27T10:00:00Z"}
    respx.get(f"{I}/assets/1").mock(side_effect=[httpx.Response(200, json=asset), httpx.Response(200, json={
        k: v for k, v in asset.items() if not k.startswith("running")})])
    a = inst.assets.get(1)
    assert (a.running, a.running_since) == ("on", "2026-11-27T10:00:00Z") and "running" not in a.extra
    assert inst.assets.get(1).running is None


@respx.mock
def test_activity_trigger_and_kind(inst):
    route = respx.get(f"{I}/activity").mock(return_value=httpx.Response(200, json={"items": [
        {"kind": "status_change", "trigger_type": "measurement", "measured_at": "2026-11-27T08:00:00Z"}],
        "next_cursor": None}))
    items = list(inst.activity.iter(kind="status_change", asset_id=4))
    assert items[0]["measured_at"] == "2026-11-27T08:00:00Z"
    assert dict(route.calls.last.request.url.params) == {"limit": "100", "asset_id": "4", "kind": "status_change"}


@respx.mock
def test_add_field_item_sends_client_uuid_only_when_given(inst):
    route = respx.post(f"{I}/executions/e/items").mock(return_value=httpx.Response(201, json={
        "uuid": "r", "route_item_uuid": "i", "data": {}, "notes": "", "status": 1, "created_at": "t"}))
    exec_ = inst.routes.execution("e")
    exec_.add_field_item(label="Leak", uuid="i")
    assert json.loads(route.calls.last.request.content)["uuid"] == "i"
    exec_.add_field_item(label="Leak")
    assert "uuid" not in json.loads(route.calls.last.request.content)


@respx.mock
def test_route_asset_checks_for(inst):
    route = respx.get(f"{I}/routes").mock(return_value=httpx.Response(200, json={"items": [
        {"uuid": "a", "name": "Pump checks", "asset_checks_for": 4}, {"uuid": "b", "name": "Daily"}],
        "total": 2, "limit": 50, "offset": 0}))
    assert [r.asset_checks_for for r in inst.routes.list(include_asset_checks=True)] == [4, None]
    assert route.calls.last.request.url.params["include_asset_checks"] == "true"
    inst.routes.list()
    assert "include_asset_checks" not in route.calls.last.request.url.params


@respx.mock
def test_route_items_carry_editor_fields(inst):
    respx.get(f"{I}/routes/r").mock(return_value=httpx.Response(200, json={"uuid": "r", "items": [
        {"uuid": "i", "instructions": ["legacy"], "instructions_html": "<div>Hold</div>", "has_own_instructions": True,
         "unit": "", "subchecks": ["Seal"]}]}))
    item = inst.routes.get("r")["items"][0]
    assert (item["instructions_html"], item["has_own_instructions"], item["subchecks"]) == ("<div>Hold</div>", True, ["Seal"])
