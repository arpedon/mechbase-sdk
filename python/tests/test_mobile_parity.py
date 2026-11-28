"""SDK: the mobile-parity endpoints — request shapes, headers, parsing with nulls, 304 and errors."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from mechbase import AuthError, ConflictError, Mechbase, ValidationError

BASE = "https://example.test"
I = f"{BASE}/api/installations/7"
USER = {"id": 1, "username": "u", "full_name": None, "email": "u@x"}
ME = {"user": {**USER, "is_staff": True}, "installations": [], "current_installation_id": 7,
      "unit_prefs": {"velocity": "in/s"}}
FINDING = {"uuid": "f-1", "status": "open", "fault_type": "bpfo", "fault_type_display": "Outer race",
           "severity": "major", "recommended_action": None, "asset_name": "Pump", "point_name": "DE",
           "created_at": "2026-11-27T10:00:00Z", "web_url": "/7/findings/f-1/"}
RESP = {"uuid": "r-1", "route_item_uuid": "it-1", "data": None, "notes": None, "status": 1,
        "created_at": "2026-11-27T10:00:00Z"}
FILE = {"uuid": "p-1", "name": "a.jpg", "kind": "photo", "file_url": "https://s/x", "created_at": "2026-11-27"}


@pytest.fixture
def inst():
    c = Mechbase(token="tok", base_url=BASE, timezone="Europe/Athens")
    yield c.for_installation(7)
    c.close()


def body(route):
    return json.loads(route.calls.last.request.content)


# --- account, push --------------------------------------------------------------


@respx.mock
def test_me_is_staff_and_partial_patch():
    respx.get(f"{BASE}/api/me/").mock(return_value=httpx.Response(200, json={**ME, "user": USER}))
    patch = respx.patch(f"{BASE}/api/me/").mock(return_value=httpx.Response(200, json=ME))
    c = Mechbase(token="tok", base_url=BASE)
    assert c.me().user.is_staff is False  # absent → False; null full_name → ""
    me = c.update_me(unit_prefs={"velocity": "in/s"})
    assert body(patch) == {"unit_prefs": {"velocity": "in/s"}}  # partial: unsent names are not nulled
    assert me.user.is_staff is True and me.unit_prefs == {"velocity": "in/s"}


@respx.mock
def test_me_names_and_unit_choices():
    choices = {"frequency": [{"value": "Hz", "label": "Hz"}, {"value": "CPM", "label": "CPM"}]}
    respx.get(f"{BASE}/api/me/").mock(side_effect=[
        httpx.Response(200, json={**ME, "user": {**USER, "first_name": "Ada", "last_name": None}, "unit_choices": choices}),
        httpx.Response(200, json=ME),  # an older server: neither
    ])
    c = Mechbase(token="tok", base_url=BASE)
    me = c.me()
    assert (me.user.first_name, me.user.last_name) == ("Ada", "")
    assert "first_name" not in me.user.extra
    assert [x["value"] for x in me.unit_choices["frequency"]] == ["Hz", "CPM"]
    old = c.me()
    assert old.user.first_name == "" and old.unit_choices == {}


@respx.mock
def test_web_session():
    route = respx.post(f"{BASE}/api/auth/web-session").mock(return_value=httpx.Response(
        200, json={"url": f"{BASE}/auth/magic/abc/", "expires_at": "2026-11-27T10:00:00Z"}))
    c = Mechbase(token="tok", base_url=BASE)
    s = c.web_session("/7/assets/4/")
    assert body(route) == {"next": "/7/assets/4/"}
    assert (s.url, s.expires_at) == (f"{BASE}/auth/magic/abc/", "2026-11-27T10:00:00Z")
    route.mock(return_value=httpx.Response(422, json={"detail": "next: must be a path on this site."}))
    with pytest.raises(ValidationError):
        c.web_session("//evil")
    route.mock(return_value=httpx.Response(403, json={"detail": "This token cannot open a web session."}))
    with pytest.raises(AuthError):
        c.web_session("/")


@respx.mock
def test_push_register_and_delete():
    reg = respx.post(f"{BASE}/api/push/devices").mock(return_value=httpx.Response(201, json={"platform": "apns"}))
    gone = respx.delete(f"{BASE}/api/push/devices/ab%2Fcd").mock(return_value=httpx.Response(204))
    c = Mechbase(token="tok", base_url=BASE)
    c.push.register("apns", "a1b2", app_version="1.4")
    assert body(reg) == {"platform": "apns", "token": "a1b2", "app_version": "1.4"}
    c.push.delete("ab/cd")  # escaped: a token can't address another path
    assert gone.called


# --- overview, alerts, activity, search, hours, notifications --------------------


@respx.mock
def test_overview_alerts_search_hours_send_timezone(inst):
    ov = respx.get(f"{I}/overview").mock(return_value=httpx.Response(200, json={"attention": [], "attention_more_count": 0}))
    al = respx.get(f"{I}/alerts").mock(return_value=httpx.Response(200, json=[]))
    se = respx.get(f"{I}/search").mock(return_value=httpx.Response(200, json={"categories": []}))
    hr = respx.get(f"{I}/hours").mock(return_value=httpx.Response(200, json={"rows": []}))
    inst.overview()
    assert ov.calls.last.request.headers["X-Timezone"] == "Europe/Athens"
    inst.alerts()
    assert "show" not in al.calls.last.request.url.params
    inst.alerts(silent=True)
    assert al.calls.last.request.url.params["show"] == "silent"
    inst.search("pump", in_="points")
    assert dict(se.calls.last.request.url.params) == {"q": "pump", "in": "points"}
    inst.hours(production_from="2026-11-01")
    assert dict(hr.calls.last.request.url.params) == {"production_from": "2026-11-01"}


@respx.mock
def test_activity_iter_follows_cursor(inst):
    route = respx.get(f"{I}/activity").mock(side_effect=[
        httpx.Response(200, json={"items": [{"kind": "comment", "actor": None}], "next_cursor": "c2"}),
        httpx.Response(200, json={"items": [{"kind": "finding", "actor": None}], "next_cursor": None}),
    ])
    assert [e["kind"] for e in inst.activity.iter(section_id=3, page_size=1)] == ["comment", "finding"]
    assert dict(route.calls[0].request.url.params) == {"limit": "1", "section_id": "3"}
    assert route.calls[1].request.url.params["cursor"] == "c2"


@respx.mock
def test_notification_settings(inst):
    respx.get(f"{I}/notification-settings").mock(return_value=httpx.Response(200, json={"severity_threshold": 3}))
    patch = respx.patch(f"{I}/notification-settings").mock(return_value=httpx.Response(200, json={}))
    respx.post(f"{I}/notification-settings/test").mock(return_value=httpx.Response(200, json={"result": "logged"}))
    assert inst.notification_settings.get()["severity_threshold"] == 3
    inst.notification_settings.update(notifications_muted=True)
    assert body(patch) == {"notifications_muted": True}
    assert inst.notification_settings.test() == "logged"


# --- dashboards ------------------------------------------------------------------


@respx.mock
def test_dashboard_etag_304_and_staff_edits(inst):
    board = {"uuid": None, "name": "Auto", "is_default": True, "is_automatic": True, "refresh_seconds": 60,
             "readiness": False, "sections": []}
    get = respx.get(f"{I}/dashboards/default").mock(side_effect=[
        httpx.Response(200, json=board, headers={"ETag": 'W/"abc"'}), httpx.Response(304)])
    first = inst.dashboards.get()
    assert first.data["name"] == "Auto" and first.etag == 'W/"abc"' and not first.not_modified
    again = inst.dashboards.get(etag=first.etag)
    assert again.not_modified and again.etag == 'W/"abc"'
    assert get.calls.last.request.headers["If-None-Match"] == 'W/"abc"'

    tiles = respx.post(f"{I}/dashboards/d-1/tiles").mock(return_value=httpx.Response(201, json=[]))
    inst.dashboards.add_tiles("d-1", "s-1", [2, 3])
    assert body(tiles) == {"section": "s-1", "point_ids": [2, 3]}
    reorder = respx.post(f"{I}/dashboards/d-1/reorder").mock(return_value=httpx.Response(204))
    inst.dashboards.reorder("d-1", [{"id": "s-1", "tiles": ["t-1"]}])
    assert body(reorder) == {"sections": [{"id": "s-1", "tiles": ["t-1"]}]}
    upd = respx.patch(f"{I}/dashboards/d-1").mock(return_value=httpx.Response(200, json={}))
    inst.dashboards.update("d-1", is_default=True)
    assert body(upd) == {"is_default": True}
    respx.post(f"{I}/dashboards").mock(return_value=httpx.Response(403, json={"detail": "Staff only."}))
    with pytest.raises(AuthError):
        inst.dashboards.create("Mine")


# --- readings & analysis -----------------------------------------------------------


@respx.mock
def test_analysis_process_compare_notes(inst):
    pt = f"{I}/measurement-points/2/measurements/766"
    an = respx.get(f"{pt}/analysis").mock(return_value=httpx.Response(200, json={"vibration": None, "thermography": None}))
    assert inst.measurements.analysis(2, 766, highpass_hz=10)["vibration"] is None
    assert dict(an.calls.last.request.url.params) == {"highpass_hz": "10"}
    pr = respx.post(f"{pt}/process").mock(return_value=httpx.Response(200, json={"cursors": []}))
    inst.measurements.process(2, 766, type="envelope", peak_count=5, cursors=[765, 766])
    assert body(pr) == {"type": "envelope", "high_pass": 0, "low_pass": 0, "db_scale": False, "peak_count": 5,
                        "cursors": [765, 766]}
    cmp_ = respx.get(f"{I}/measurement-points/2/compare").mock(side_effect=[
        httpx.Response(200, json={"cursors": []}, headers={"ETag": '"e1"'}), httpx.Response(304)])
    r = inst.measurements.compare(2, [765, 766], spectrum="accel")
    assert dict(cmp_.calls.last.request.url.params) == {"seq": "765,766", "spectrum": "accel"}
    assert inst.measurements.compare(2, [765, 766], etag=r.etag).not_modified
    notes = respx.patch(f"{pt}/").mock(return_value=httpx.Response(200, json={
        "uuid": "u", "measurement_point_id": 2, "point_sequence": None, "data": {}, "status": "good",
        "notes": None, "created_at": "2026-11-27T10:00:00Z"}))
    m = inst.measurements.set_notes(2, 766, "Loose guard")
    assert body(notes) == {"notes": "Loose guard"} and m.notes == "" and m.point_sequence is None


@respx.mock
def test_compare_bad_seq_is_validation_error(inst):
    respx.get(f"{I}/measurement-points/2/compare").mock(
        return_value=httpx.Response(422, json={"detail": "seq must be comma-separated point_sequence numbers."}))
    with pytest.raises(ValidationError):
        inst.measurements.compare(2, [])


@respx.mock
def test_asset_trend_fault_record_flip_rebuild(inst):
    tr = respx.get(f"{I}/assets/1/trend").mock(return_value=httpx.Response(200, json={"series": []}))
    inst.assets.trend(1, type="VB")
    assert tr.calls.last.request.url.params["type"] == "VB"
    fr = respx.get(f"{I}/assets/1/fault-record").mock(return_value=httpx.Response(200, json={"rows": []}))
    inst.assets.fault_record(1, "2026-11-27T10:00:00+02:00", point_id=2)
    assert dict(fr.calls.last.request.url.params) == {"at": "2026-11-27T10:00:00+02:00", "point": "2"}
    respx.post(f"{I}/assets/1/production/flip").mock(return_value=httpx.Response(200, json={"state": None, "last_ping": None}))
    assert inst.assets.flip_production(1) == {"state": None, "last_ping": None}
    respx.post(f"{I}/assets/1/checklist/rebuild").mock(return_value=httpx.Response(422, json={"detail": "A run is open."}))
    with pytest.raises(ValidationError):
        inst.assets.rebuild_checklist(1)


@respx.mock
def test_point_analysis_fields_and_baselines(inst):
    point = {"uuid": "p", "point_id": 2, "name": "DE", "asset_id": 1, "status": 1, "nominal_rpm": None,
             "bearing": None, "speed_ratio": None, "envelope_band_low": None, "has_own_instructions": None}
    patch = respx.patch(f"{I}/measurement-points/2").mock(return_value=httpx.Response(200, json=point))
    p = inst.measurement_points.update(2, nominal_rpm=1480, bearing=None, name=None)
    assert body(patch) == {"nominal_rpm": 1480, "bearing": None}  # None clears an analysis field, not the name
    assert p.speed_ratio == 1.0 and p.nominal_rpm is None and p.has_own_instructions is False
    inst.measurement_points.update(2, location="DE")
    assert body(patch) == {"location": "DE"}
    bl = respx.post(f"{I}/measurement-points/2/baseline").mock(return_value=httpx.Response(202, json={"detail": "Queued."}))
    assert inst.measurement_points.create_baseline(2, "2026-10-01") == "Queued."
    assert body(bl) == {"refit_from": "2026-10-01"}
    respx.delete(f"{I}/measurement-points/2/baseline").mock(return_value=httpx.Response(200, json={"detail": "Cleared."}))
    assert inst.measurement_points.clear_baseline(2) == "Cleared."
    respx.get(f"{I}/measurement-points/2/baseline/preview").mock(return_value=httpx.Response(200, json={"eligible": 4, "fit_min": 20}))
    assert inst.measurement_points.baseline_preview(2, since="2026-10-01")["fit_min"] == 20


# --- findings, bearings ---------------------------------------------------------------


@respx.mock
def test_finding_create_choices_and_bearings(inst):
    create = respx.post(f"{I}/findings/").mock(return_value=httpx.Response(201, json=FINDING))
    f = inst.findings.create(point_id=2, point_sequence=766, fault_type="bpfo", severity="major", hz=107.5,
                             signal="envelope", df=0.25)
    assert body(create) == {"point_id": 2, "point_sequence": 766, "fault_type": "bpfo", "severity": "major",
                            "recommended_action": "", "comment": "", "hz": 107.5, "unit": "", "signal": "envelope",
                            "df": 0.25}
    assert f.recommended_action == ""  # null → ""
    ch = respx.get(f"{I}/findings/choices/").mock(return_value=httpx.Response(200, json={
        "fault_types": [], "severities": [], "suggested_fault_type": None}))
    inst.findings.choices()
    assert dict(ch.calls.last.request.url.params) == {}
    bs = respx.get(f"{I}/bearings").mock(return_value=httpx.Response(200, json={"own": [], "results": [], "library_count": 9}))
    inst.bearings.search("6205")
    assert dict(bs.calls.last.request.url.params) == {"q": "6205"}
    inst.bearings.search(order=3.58, sideband="1x")
    assert dict(bs.calls.last.request.url.params) == {"order": "3.58", "sideband": "1x"}
    new = respx.post(f"{I}/bearings").mock(return_value=httpx.Response(201, json={}))
    inst.bearings.create("6205-2RS", bpfo=3.58, bpfi=5.42, bsf=2.36, ftf=0.4)
    assert body(new)["designation"] == "6205-2RS" and body(new)["bpfo"] == 3.58


# --- routes ------------------------------------------------------------------------------


@respx.mock
def test_route_crud_items_reorder_photo_history(inst, tmp_path):
    create = respx.post(f"{I}/routes").mock(return_value=httpx.Response(201, json={"uuid": "r-1", "items": []}))
    inst.routes.create("Daily", [{"uuid": "i-1", "label": "Oil"}], uuid="r-1")
    assert body(create) == {"uuid": "r-1", "name": "Daily", "description": "", "items": [{"uuid": "i-1", "label": "Oil"}]}
    patch = respx.patch(f"{I}/routes/r-1").mock(return_value=httpx.Response(200, json={
        "uuid": "r-1", "name": "Night", "description": None}))
    assert inst.routes.update("r-1", name="Night").description == ""
    assert body(patch) == {"name": "Night"}
    respx.delete(f"{I}/routes/r-1").mock(return_value=httpx.Response(409, json={"detail": "A run is in progress."}))
    with pytest.raises(ConflictError):
        inst.routes.delete("r-1")
    item = respx.post(f"{I}/routes/r-1/items").mock(return_value=httpx.Response(200, json={"uuid": "i-2"}))
    inst.routes.add_item("r-1", "Temp", item_type="numerical", unit="°C", uuid="i-2")
    assert body(item) == {"uuid": "i-2", "label": "Temp", "item_type": "numerical", "unit": "°C"}
    ro = respx.post(f"{I}/routes/r-1/items/reorder").mock(return_value=httpx.Response(200, json={"items": [{"uuid": "i-2", "check_id": 1}]}))
    assert inst.routes.reorder_items("r-1", [{"uuid": "i-2", "position": 0, "zone_id": None}]) == [{"uuid": "i-2", "check_id": 1}]
    assert body(ro) == {"items": [{"uuid": "i-2", "position": 0, "zone_id": None}]}
    photo = respx.post(f"{I}/routes/r-1/items/i-2/photos").mock(return_value=httpx.Response(201, json=FILE))
    inst.routes.set_item_photo("r-1", "i-2", b"jpg", uuid="ph-1")
    req = photo.calls.last.request
    assert b'name="uuid"' in req.content and b"ph-1" in req.content
    respx.get(f"{I}/routes/r-1/items/i-2/history").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    assert inst.routes.item_history("r-1", "i-2")["total"] == 0
    ex = respx.get(f"{I}/routes/r-1/executions").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    inst.routes.executions("r-1", limit=5)
    assert dict(ex.calls.last.request.url.params) == {"limit": "5", "offset": "0"}


@respx.mock
def test_report_amend_and_response_notes(inst, tmp_path):
    ex = inst.routes.execution("e-1")
    respx.get(f"{I}/executions/e-1/report").mock(return_value=httpx.Response(200, json={"can_amend": True}))
    assert ex.report()["can_amend"] is True
    ans = respx.post(f"{I}/executions/e-1/amend/it-1/answer").mock(return_value=httpx.Response(201, json=RESP))
    r = ex.amend_answer("it-1", {"passed": True}, idempotency_key="k-1")
    assert ans.calls.last.request.headers["X-Idempotency-Key"] == "k-1"
    assert body(ans) == {"data": {"passed": True}, "notes": ""} and r.data == {} and r.notes == ""
    reading = respx.post(f"{I}/executions/e-1/amend/it-1/reading").mock(return_value=httpx.Response(201, json=RESP))
    img = tmp_path / "a.jpg"
    img.write_bytes(b"jpg")
    ex.amend_reading("it-1", value=2.5, comment="late", images=[img], data_file=b"dr", idempotency_key="k-2")
    req = reading.calls.last.request
    assert req.headers["X-Idempotency-Key"] == "k-2"
    assert b'name="images"; filename="a.jpg"' in req.content and b'name="data_file"' in req.content
    assert b'name="value"' in req.content and b"2.5" in req.content
    respx.delete(f"{I}/executions/e-1/amend/it-1/photos/p-1").mock(return_value=httpx.Response(204))
    assert ex.amend_remove_photo("it-1", "p-1") is None
    notes = respx.patch(f"{I}/responses/r-1").mock(return_value=httpx.Response(200, json=RESP))
    inst.routes.set_response_notes("r-1", "Belt worn")
    assert body(notes) == {"notes": "Belt worn"}


@respx.mock
def test_non_conformities_and_survey(inst):
    nc = respx.get(f"{I}/non-conformities").mock(return_value=httpx.Response(200, json={"items": [], "total": 0}))
    inst.non_conformities.list(asset_id=4)
    assert dict(nc.calls.last.request.url.params) == {"status": "open", "asset_id": "4", "limit": "50", "offset": "0"}
    res = respx.post(f"{I}/non-conformities/r-1/resolve").mock(return_value=httpx.Response(409, json={"detail": "Resolved by someone else."}))
    with pytest.raises(ConflictError):
        inst.non_conformities.resolve("r-1", comment="fixed")
    assert body(res) == {"comment": "fixed"}
    sv = respx.post(f"{I}/surveys").mock(return_value=httpx.Response(201, json={
        "route": {"uuid": "r-9", "name": "Survey", "description": "", "section": {"section_id": None, "name": ""}},
        "execution": {"uuid": "e-9", "route_uuid": "r-9", "status": "in_progress", "started_at": None,
                      "completed_at": None, "session_id": "s"}}))
    h = inst.routes.start_survey("Walkdown", uuid="e-9")
    assert body(sv) == {"name": "Walkdown", "uuid": "e-9"}
    assert h.uuid == "e-9" and h.route["uuid"] == "r-9" and h.execution.started_at is None


# --- devices, zones -------------------------------------------------------------------------


@respx.mock
def test_device_commissioning(inst):
    lk = respx.get(f"{I}/devices/lookup/bal-1").mock(return_value=httpx.Response(200, json={"state": "claim", "name": None}))
    assert inst.devices.lookup("bal-1")["state"] == "claim"
    claim = respx.post(f"{I}/devices").mock(return_value=httpx.Response(201, json={"node_uuid": "n-1"}))
    inst.devices.claim("bal-1", name="Boiler")
    assert body(claim) == {"balena_uuid": "bal-1", "name": "Boiler"}
    inst.devices.claim("bal-1")
    assert body(claim) == {"balena_uuid": "bal-1"}
    respx.post(f"{I}/devices/n-1/credentials").mock(return_value=httpx.Response(202, json={"token_push": {"state": "queued"}}))
    assert inst.devices.resend_credentials("n-1")["token_push"]["state"] == "queued"
    respx.get(f"{I}/devices/n-1/channels").mock(return_value=httpx.Response(200, json=[{"slots": None, "channels": []}]))
    assert inst.devices.channels("n-1")[0]["slots"] is None
    grp = respx.post(f"{I}/devices/n-1/groups").mock(return_value=httpx.Response(201, json={}))
    inst.devices.create_group("n-1", group_name="hat", hardware_type="hat", interval=600)
    assert body(grp) == {"group_name": "hat", "hardware_type": "hat", "interval": 600}
    respx.get(f"{I}/devices/lookup/bal-2").mock(return_value=httpx.Response(403, json={"detail": "Service tokens cannot claim."}))
    with pytest.raises(AuthError):
        inst.devices.lookup("bal-2")
    assert lk.calls.last.request.headers["X-Timezone"] == "Europe/Athens"


@respx.mock
def test_zone_documents_and_photos(inst):
    respx.get(f"{I}/zones/3/documents").mock(return_value=httpx.Response(200, json=[{"uuid": "d", "inherited": True}]))
    assert inst.zones.documents(3)[0]["inherited"] is True
    up = respx.post(f"{I}/zones/3/documents").mock(return_value=httpx.Response(201, json={"uuid": "d-2"}))
    inst.zones.add_document(3, b"%PDF", filename="m.pdf", kind="manual", uuid="d-2")
    assert b'filename="m.pdf"' in up.calls.last.request.content and b"manual" in up.calls.last.request.content
    ph = respx.post(f"{I}/zones/3/photos").mock(return_value=httpx.Response(201, json={"uuid": "p"}))
    inst.zones.add_photo(3, b"jpg")
    assert b'name="uuid"' not in ph.calls.last.request.content
    respx.delete(f"{I}/zones/3/photos/p").mock(return_value=httpx.Response(204))
    inst.zones.delete_photo(3, "p")


# --- review fixes ------------------------------------------------------------------------------


@respx.mock
def test_point_upsert_sends_no_analysis_fields(inst):
    put = respx.put(f"{I}/measurement-points").mock(return_value=httpx.Response(200, json={
        "uuid": "p", "point_id": 2, "name": "DE", "asset_id": 1, "status": 1}))
    inst.measurement_points.upsert(external_id="DE-1", name="DE")
    assert body(put) == {"external_id": "DE-1", "name": "DE"}
    with pytest.raises(TypeError):
        inst.measurement_points.upsert(external_id="DE-1", nominal_rpm=1480)  # the server 422s these on PUT
    create = respx.post(f"{I}/measurement-points").mock(return_value=httpx.Response(201, json={
        "uuid": "p", "point_id": 2, "name": "DE", "asset_id": 1, "status": 1}))
    inst.measurement_points.create(name="DE", asset_id=1, nominal_rpm=1480)
    assert body(create) == {"name": "DE", "asset_id": 1, "nominal_rpm": 1480}


@respx.mock
def test_push_delete_is_best_effort_on_404_only():
    route = respx.delete(f"{BASE}/api/push/devices/a1").mock(return_value=httpx.Response(404, json={"detail": "Not found."}))
    c = Mechbase(token="tok", base_url=BASE)
    assert c.push.delete("a1") is None
    route.mock(return_value=httpx.Response(403, json={"detail": "Token not authorized."}))
    with pytest.raises(AuthError):
        c.push.delete("a1")


def test_local_timezone_validates_and_canonicalises(monkeypatch):
    from mechbase._http import local_timezone

    monkeypatch.setenv("TZ", "EST5EDT,M3.2.0,M11.1.0")  # a POSIX rule: fall back to /etc/localtime
    monkeypatch.setattr("os.path.realpath", lambda p: "/usr/share/zoneinfo/posix/Europe/Athens")
    assert local_timezone() == "Europe/Athens"
    monkeypatch.setattr("os.path.realpath", lambda p: "/usr/share/zoneinfo/right/America/New_York")
    assert local_timezone() == "America/New_York"
    monkeypatch.setattr("os.path.realpath", lambda p: "/var/db/timezone/zoneinfo/Not/AZone")
    assert local_timezone() is None
    monkeypatch.setenv("TZ", "Europe/Athens")
    assert local_timezone() == "Europe/Athens"
    # A case-insensitive disk (macOS) opens "europe/athens": the canonical spelling goes out, and a name
    # that opens but is no zone is dropped.
    from mechbase import _http

    monkeypatch.setattr(_http, "ZoneInfo", lambda name: None)
    assert _http._zone_name("europe/athens") == "Europe/Athens"
    assert _http._zone_name("posix/europe/athens") == "Europe/Athens"
    assert _http._zone_name("Foo/Bar") is None


@respx.mock
def test_amend_reading_closes_opened_files_when_a_later_one_fails(inst, tmp_path, monkeypatch):
    opened = []
    real_open = open

    def tracking_open(path, mode="r", *a, **k):
        fh = real_open(path, mode, *a, **k)
        opened.append(fh)
        return fh

    monkeypatch.setattr("builtins.open", tracking_open)
    img = tmp_path / "a.jpg"
    img.write_bytes(b"jpg")
    route = respx.post(f"{I}/executions/e-1/amend/it-1/reading")
    with pytest.raises(FileNotFoundError):
        inst.routes.execution("e-1").amend_reading("it-1", images=[img, tmp_path / "missing.jpg"])
    assert opened and all(fh.closed for fh in opened) and not route.called
