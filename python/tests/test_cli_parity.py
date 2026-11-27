"""CLI: the mobile-parity commands, offline via respx — output, request shapes and exit codes."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from mechbase.cli import main

BASE = "https://example.test"
I = f"{BASE}/api/installations/7"
R = "11111111-2222-3333-4444-555555555555"
NODE = "6f1e2d3c-4b5a-4968-8776-5a4b3c2d1e0f"
ALERT = {"section_id": 1, "section_name": "Boilers", "zone_id": None, "zone_name": None, "asset_id": 4,
         "asset_uuid": "a", "name": "Pump 4", "status": 4, "is_silent": False, "reason": "DE rms 7.9",
         "trigger_name": "DE", "trigger_point_id": 2, "trigger_route": "", "silent_points": [],
         "alert_since": "2026-11-27T08:00:00Z"}
DEVICE = {"node_uuid": NODE, "name": "Node A", "is_online": False, "last_seen_at": None, "groups": [], "tunnels": [],
          "health_warnings": [], "token_push": {"state": "queued"}}


@pytest.fixture(autouse=True)
def cli_env(monkeypatch, tmp_path):
    for k, v in {"XDG_CONFIG_HOME": str(tmp_path), "MECHBASE_TOKEN": "tok", "MECHBASE_URL": BASE,
                 "MECHBASE_INSTALLATION": "7"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.chdir(tmp_path)


def out(capsys) -> str:
    return capsys.readouterr().out


def exits(argv) -> SystemExit:
    with pytest.raises(SystemExit) as e:
        main(argv)
    return e.value


@respx.mock
def test_overview_and_alerts(capsys):
    respx.get(f"{I}/overview").mock(return_value=httpx.Response(200, json={
        "status_summary": {"total": 12, "nominal": 9, "elevated": 1, "warning": 1, "critical": 1, "attention": 3},
        "briefing": {}, "last_reading_at": None, "attention": [ALERT], "attention_more_count": 2, "silent_count": 1,
        "running_executions": [{"execution_uuid": "e-1", "route_uuid": R, "route_name": "Daily", "started_at": None,
                                "executed_by": None, "done": 3, "total": 8, "last_completed_execution_uuid": None}],
        "routes": [], "back_to_normal": [], "sections": []}))
    main(["overview"])
    o = out(capsys)
    assert "12 assets · 9 good · 1 elevated · 1 minor · 1 major · 1 silent" in o
    assert "+2 more: mechbase alerts" in o and "Pump 4" in o and "major" in o and "3/8" in o

    al = respx.get(f"{I}/alerts").mock(return_value=httpx.Response(200, json=[{**ALERT, "is_silent": True}]))
    main(["alerts", "--silent"])
    assert al.calls.last.request.url.params["show"] == "silent" and "silent" in out(capsys)
    al.mock(return_value=httpx.Response(200, json=[]))
    main(["alerts"])
    assert out(capsys).strip() == "Nothing needs attention."


@respx.mock
def test_activity_groups_by_day_and_stops_at_limit(capsys):
    route = respx.get(f"{I}/activity").mock(return_value=httpx.Response(200, json={"items": [
        {"kind": "comment", "timestamp": "2026-11-27T10:00:00+00:00", "title": "Note on Pump 4", "detail": "noisy",
         "actor": {"id": 1, "name": "Ann"}},
        {"kind": "status_change", "timestamp": "2026-11-26T10:00:00+00:00", "title": "Pump 4 → major", "detail": "",
         "actor": None},
        {"kind": "finding", "timestamp": "2026-11-25T10:00:00+00:00", "title": "never shown", "detail": "", "actor": None},
    ], "next_cursor": "more"}))
    main(["activity", "-n", "2"])
    o = out(capsys)
    assert "Note on Pump 4 — noisy (Ann)" in o and "Pump 4 → major" in o and "never shown" not in o
    assert o.count("2026-11-") == 2 and route.call_count == 1


@respx.mock
def test_search_and_hours(capsys):
    se = respx.get(f"{I}/search").mock(return_value=httpx.Response(200, json={
        "query": "pump", "category": None, "total_count": 2,
        "categories": [{"key": "assets", "slug": "assets", "label": "Assets", "count": 1, "selected": False},
                       {"key": "comments", "slug": "comments", "label": "Comments", "count": 1, "selected": False},
                       {"key": "zones", "slug": "zones", "label": "Zones", "count": 0, "selected": False}],
        "assets": [{"asset_id": 4, "uuid": "a", "name": "Pump 4", "section_name": "Boilers", "status": 1}],
        "comments": [{"comment_id": 9, "body_text": "pump  noisy\n again", "author_name": "Ann", "asset_name": "Pump 4"}]}))
    main(["search", "pump", "--in", "assets"])
    o = out(capsys)
    assert se.calls.last.request.url.params["in"] == "assets"
    assert "2 results: assets 1, comments 1" in o and "4  Pump 4  · Boilers" in o and "9  pump noisy again  · Pump 4" in o

    respx.get(f"{I}/hours").mock(return_value=httpx.Response(200, json={
        "window_start": "2026-11-27T00:00:00+02:00", "window_end": "2026-11-27T12:00:00+02:00", "stale_hours": 6,
        "rows": [{"asset_id": 4, "asset_name": "Pump 4", "state": None, "last_ping": None, "range_hours": 7.25,
                  "lifetime_hours": 1203.4, "segments": []}]}))
    main(["hours"])
    o = out(capsys)
    assert "Pump 4" in o and "unknown" in o and "7.2" in o and "never" in o


@respx.mock
def test_dashboards_and_board_tiles(capsys):
    respx.get(f"{I}/dashboards").mock(return_value=httpx.Response(200, json=[
        {"uuid": None, "name": "All monitored points", "is_default": False, "is_automatic": True},
        {"uuid": "d-123", "name": "Boilers", "is_default": True, "is_automatic": False}]))
    main(["dashboards"])
    assert "(automatic)" in out(capsys)
    tile = {"uuid": "t", "label": "Pump 4 · DE", "point_id": 2, "value": 2.345, "unit": "mm/s", "decimals": 1,
            "status": 3, "status_label": "Warning", "stale_since": None, "state": "on", "measured_at": None}
    board = respx.get(f"{I}/dashboards/d-123").mock(return_value=httpx.Response(200, json={
        "uuid": "d-123", "name": "Boilers", "is_automatic": False, "sections": [
            {"title": "Boiler room", "meta": "", "status_label": "Warning",
             "tiles": [tile, {**tile, "label": "Fan", "value": None, "stale_since": "2026-11-26T00:00:00Z"}]}]}))
    main(["dashboard", "boilers"])
    o = out(capsys)
    assert board.called and "2.3 mm/s" in o and "Warning" in o and "—" in o and "STALE" in o
    assert exits(["dashboard", "nope"]).code == "No dashboard matches nope."


@respx.mock
def test_reading_analysis_summary(capsys):
    freq = [i * 0.5 for i in range(400)]
    vel = [0.0] * 400
    vel[200] = 3.0  # 100 Hz: 2×50 electrical
    respx.get(f"{I}/measurement-points/2/measurements/766/analysis").mock(return_value=httpx.Response(200, json={
        "uuid": "u", "point_id": 2, "point_sequence": 766, "created_at": "2026-11-27T10:00:00Z", "status": "warning",
        "notes": "", "transducer_type": "VB", "data": {"rms": 2.3456, "spectrum": [1, 2], "ok": True},
        "units": {"velocity": "mm/s", "acceleration": "g", "frequency": "Hz", "frequency_scale": 1},
        "vibration": {"n_lines": 400, "freq_resolution_hz": 0.5, "fmax_hz": 200, "env_band_hz": None,
                      "spectrum": {"freq_hz": freq, "velocity": vel, "accel": [], "envelope": []},
                      "bearing_markers": [{"kind": "bpfo", "label": "BPFO", "hz": 87.3, "harmonic": 1},
                                          {"kind": "bpfo", "label": "2×BPFO", "hz": 174.6, "harmonic": 2}],
                      "order": None, "thresholds": {}},
        "thermography": None, "attachments": []}))
    main(["reading", "analysis", "2", "766", "--peaks", "3"])
    o = out(capsys)
    assert "WARNING · VB" in o and "rms  2.346" in o and "spectrum" not in o.split("Spectrum")[0]
    assert "400 lines, 0.5 Hz/line" in o and "2×50 Hz (electrical)" in o and "(mm/s)" in o
    assert "BPFO 87.3 Hz" in o and "2×BPFO" not in o
    main(["reading", "analysis", "2", "766", "--json"])
    j = json.loads(out(capsys))
    assert j["peaks"][0]["hz"] == 100.0 and len(j["bearing_markers"]) == 1


@respx.mock
def test_reading_analysis_without_vibration(capsys):
    respx.get(f"{I}/measurement-points/5/measurements/1/analysis").mock(return_value=httpx.Response(200, json={
        "uuid": "u", "point_id": 5, "point_sequence": 1, "created_at": "2026-11-27T10:00:00Z", "status": "good",
        "transducer_type": "IR", "data": {}, "units": {}, "vibration": None, "attachments": [],
        "thermography": {"thermograms": [{"uuid": "t"}], "hotspot_count": 2, "worst_delta_t": 12.5}}))
    main(["reading", "analysis", "5", "1"])
    o = out(capsys)
    assert "1 image(s), 2 hot spot(s), worst ΔT 12.5" in o and "peaks" not in o


@respx.mock
def test_runs_report_ncs_resolve(capsys):
    respx.get(f"{I}/routes").mock(return_value=httpx.Response(200, json={"items": [
        {"uuid": R, "name": "Daily round", "description": None}], "total": 1}))
    respx.get(f"{I}/routes/{R}/executions").mock(return_value=httpx.Response(200, json={"items": [
        {"uuid": "e-1", "number": 12, "status": "completed", "started_at": "2026-11-27T07:00:00Z",
         "executed_by": None, "answered_count": 8, "passed_count": 7, "non_conformity_count": 1}], "total": 1}))
    main(["runs", "daily round"])
    o = out(capsys)
    assert "12" in o and "e-1" in o and "completed" in o

    respx.get(f"{I}/executions/e-1/report").mock(return_value=httpx.Response(200, json={
        "execution": {"number": 12, "status": "completed", "started_at": None, "executed_by": {"id": 1, "name": "Ann"}},
        "route": {"name": "Daily round"}, "can_amend": True,
        "totals": {"checks": 9, "answered": 8, "passed": 7, "non_conformities": 1},
        "groups": [], "missing": [{"check_id": 9, "label": "Guard fitted", "asset_name": None}],
        "exceptions": [{"response_uuid": "r-1", "route_item_uuid": "i", "name": "Oil level", "status": 3, "resolved": False}]}))
    main(["run", "report", "e-1"])
    o = out(capsys)
    assert "Daily round · run 12 · completed · Ann" in o and "8/9 answered · 7 passed · 1 non-conformities" in o
    assert "Oil level" in o and "#9 Guard fitted" in o

    nc = {"response_uuid": "r-1", "route_name": "Daily round", "label": "Oil level", "status": 3, "notes": None,
          "created_at": "2026-11-27T07:10:00Z", "resolved_at": None}
    lst = respx.get(f"{I}/non-conformities").mock(return_value=httpx.Response(200, json={"items": [nc], "total": 1}))
    main(["ncs", "--asset", "4"])
    assert lst.calls.last.request.url.params["asset_id"] == "4" and "Oil level" in out(capsys)
    res = respx.post(f"{I}/non-conformities/r-1/resolve").mock(return_value=httpx.Response(200, json=nc))
    main(["nc", "resolve", "r-1", "--comment", "topped up"])
    assert json.loads(res.calls.last.request.content) == {"comment": "topped up"}
    assert "Resolved Oil level" in out(capsys)
    res.mock(return_value=httpx.Response(409, json={"detail": "Resolved by someone else."}))
    assert exits(["nc", "resolve", "r-1"]).code == "Error: 409 Resolved by someone else."


@respx.mock
def test_survey_and_route_lifecycle(capsys, tmp_path):
    respx.post(f"{I}/surveys").mock(return_value=httpx.Response(201, json={
        "route": {"uuid": R, "name": "Walkdown", "description": "", "section": {}},
        "execution": {"uuid": "e-9", "route_uuid": R, "status": "in_progress", "started_at": None,
                      "completed_at": None, "session_id": "s"}}))
    main(["survey", "new", "Walkdown"])
    assert "Started survey Walkdown" in out(capsys)

    create = respx.post(f"{I}/routes").mock(return_value=httpx.Response(201, json={
        "uuid": R, "name": "Night", "items": [{}, {}, {}]}))
    (tmp_path / "checks.json").write_text('[{"label": "Temp", "item_type": "numerical", "unit": "°C"}]')
    main(["route", "new", "Night", "--check", "Oil", "--check", "Guard", "--file", "checks.json"])
    assert json.loads(create.calls.last.request.content)["items"] == [
        {"label": "Oil"}, {"label": "Guard"}, {"label": "Temp", "item_type": "numerical", "unit": "°C"}]
    assert "with 3 check(s)" in out(capsys)
    assert exits(["route", "new", "Empty"]).code == "Give at least one --check or a --file of checks."

    ren = respx.patch(f"{I}/routes/{R}").mock(return_value=httpx.Response(200, json={
        "uuid": R, "name": "Night shift", "description": ""}))
    main(["route", "rename", R, "Night shift"])
    assert json.loads(ren.calls.last.request.content) == {"name": "Night shift"} and "Night shift" in out(capsys)

    gone = respx.delete(f"{I}/routes/{R}").mock(return_value=httpx.Response(204))
    respx.get(f"{I}/routes").mock(return_value=httpx.Response(200, json={"items": [{"uuid": R, "name": "Night shift"}]}))
    main(["route", "delete", "night shift", "-y"])
    assert gone.called and "Deleted route Night shift." in out(capsys)
    gone.mock(return_value=httpx.Response(409, json={"detail": "A run is in progress."}))
    assert exits(["route", "delete", R, "-y"]).code == "Error: 409 A run is in progress."


@respx.mock
def test_check_add_rm_mv(capsys, monkeypatch):
    items = [{"uuid": "aaaa-1", "check_id": 1, "label": "Oil"}, {"uuid": "bbbb-2", "check_id": 2, "label": "Guard"}]
    respx.get(f"{I}/routes/{R}").mock(return_value=httpx.Response(200, json={"uuid": R, "items": items}))
    add = respx.post(f"{I}/routes/{R}/items").mock(return_value=httpx.Response(201, json={"check_id": 3, "label": "Temp"}))
    main(["check", "add", R, "Temp", "--type", "numerical", "--unit", "°C"])
    assert json.loads(add.calls.last.request.content) == {"label": "Temp", "item_type": "numerical", "unit": "°C"}
    assert "Added check #3 Temp." in out(capsys)

    rm = respx.delete(f"{I}/routes/{R}/items/bbbb-2").mock(return_value=httpx.Response(204))
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert exits(["check", "rm", R, "#2"]).code == "Cancelled." and not rm.called
    main(["check", "rm", R, "guard", "-y"])
    assert rm.called and "Removed check #2 Guard." in out(capsys)

    mv = respx.post(f"{I}/routes/{R}/items/reorder").mock(return_value=httpx.Response(200, json={"items": [
        {"uuid": "bbbb-2", "check_id": 1}, {"uuid": "aaaa-1", "check_id": 2}]}))
    main(["check", "mv", R, "2", "0"])
    assert json.loads(mv.calls.last.request.content) == {"items": [{"uuid": "bbbb-2", "position": 0}]}
    assert "now check #1" in out(capsys)
    assert exits(["check", "mv", R, "nope", "0"]).code == "No check matches nope."


@respx.mock
def test_device_lookup_claim_channels_creds(capsys):
    lk = respx.get(f"{I}/devices/lookup/bal-1").mock(return_value=httpx.Response(200, json={
        "state": "taken", "node_uuid": NODE, "name": "Node A", "installation_id": 9, "installation_name": "Other plant",
        "is_online": None}))
    main(["device", "lookup", "bal-1"])
    o = out(capsys)
    assert lk.called and "claimed by Other plant" in o and "offline" in o
    lk.mock(return_value=httpx.Response(200, json={"state": "claim", "node_uuid": NODE, "name": None,
                                                    "installation_id": None, "installation_name": None, "is_online": None}))
    main(["device", "lookup", "bal-1"])
    assert "free to claim" in out(capsys)

    claim = respx.post(f"{I}/devices").mock(return_value=httpx.Response(201, json=DEVICE))
    main(["device", "claim", "bal-1", "--name", "Node A"])
    assert json.loads(claim.calls.last.request.content) == {"balena_uuid": "bal-1", "name": "Node A"}
    assert "Claimed Node A" in out(capsys)
    claim.mock(return_value=httpx.Response(403, json={"detail": "Service tokens cannot claim devices."}))
    assert exits(["device", "claim", "bal-1"]).code == "Error: 403 Service tokens cannot claim devices."

    respx.get(f"{I}/devices").mock(return_value=httpx.Response(200, json=[DEVICE]))
    respx.get(f"{I}/devices/{NODE}/channels").mock(return_value=httpx.Response(200, json=[
        {"uuid": "g", "name": "hat", "hardware_type": "hat", "slots": 16, "channels": [
            {"channel": 0, "used": True, "point_id": 2, "point_name": "DE", "asset_name": "Pump 4", "sensor": "accelerometer", "state": "ok"},
            {"channel": 1, "used": False, "point_id": None, "point_name": None, "asset_name": None, "sensor": None, "state": None}]}]))
    main(["device", "channels", "node a"])
    o = out(capsys)
    assert "1 used of 16" in o and "2 Pump 4 · DE" in o and "free" in o
    respx.post(f"{I}/devices/{NODE}/credentials").mock(return_value=httpx.Response(202, json=DEVICE))
    main(["device", "creds", "6f1e"])
    assert "Credentials for Node A: queued." in out(capsys)


@respx.mock
def test_bearing_search_and_finding_new(capsys):
    b = {"uuid": "b-1", "designation": "6205-2RS", "manufacturer": None, "source": "library", "bpfo": 3.58,
         "bpfi": 5.42, "bsf": 2.36, "ftf": 0.4, "match": "BPFO"}
    bs = respx.get(f"{I}/bearings").mock(return_value=httpx.Response(200, json={"own": [], "results": [b], "library_count": 1}))
    main(["bearing", "search", "6205"])
    assert bs.calls.last.request.url.params["q"] == "6205" and "6205-2RS" in out(capsys)
    main(["bearing", "search", "--order", "3.58"])
    assert "MATCH" in out(capsys)

    respx.get(f"{I}/findings/choices/").mock(return_value=httpx.Response(200, json={
        "fault_types": [{"value": "bpfo", "label": "Outer race"}], "severities": [{"value": "major", "label": "Major"}]}))
    e = exits(["finding", "new", "2", "766"])
    assert e.code == "Give --fault and --severity." and "Fault types: bpfo" in out(capsys)
    create = respx.post(f"{I}/findings/").mock(return_value=httpx.Response(201, json={
        "uuid": "f-1", "status": "open", "fault_type": "bpfo", "fault_type_display": "Outer race", "severity": "major",
        "asset_name": "Pump 4", "point_name": "DE", "created_at": "2026-11-27T10:00:00Z"}))
    main(["finding", "new", "2", "766", "--fault", "bpfo", "--severity", "major", "--hz", "87.3"])
    sent = json.loads(create.calls.last.request.content)
    assert sent["point_sequence"] == 766 and sent["hz"] == 87.3 and "due_by" not in sent
    assert "Recorded Outer race (major) on Pump 4 · DE: f-1" in out(capsys)
    create.mock(return_value=httpx.Response(422, json={"detail": "fault_type: Select a valid choice."}))
    assert exits(["finding", "new", "2", "766", "--fault", "x", "--severity", "major"]).code.startswith("Error: 422")


@respx.mock
def test_notify_and_me_set_units(capsys):
    settings = {"severity_threshold": 3, "status_changes": True, "route_completions": False, "exports": True,
                "notifications_muted": False, "threshold_choices": [{"value": 3, "label": "Warning and worse"}]}
    respx.get(f"{I}/notification-settings").mock(return_value=httpx.Response(200, json=settings))
    main(["notify", "show"])
    o = out(capsys)
    assert "3 (Warning and worse)" in o and "route_completions    off" in o
    patch = respx.patch(f"{I}/notification-settings").mock(return_value=httpx.Response(200, json=settings))
    main(["notify", "set", "notifications_muted=on", "severity_threshold=4"])
    assert json.loads(patch.calls.last.request.content) == {"notifications_muted": True, "severity_threshold": 4}
    out(capsys)
    assert exits(["notify", "set", "loud=on"]).code.startswith("Unknown setting loud")
    respx.post(f"{I}/notification-settings/test").mock(return_value=httpx.Response(200, json={"result": "sent"}))
    main(["notify", "test"])
    assert "Test e-mail sent." in out(capsys)

    me = respx.patch(f"{BASE}/api/me/").mock(return_value=httpx.Response(200, json={
        "user": {"id": 1, "username": "u", "full_name": "", "email": "u@x"}, "installations": [],
        "unit_prefs": {"velocity": "in/s", "acceleration": "g"}}))
    main(["me", "set-units", "velocity=in/s"])
    assert json.loads(me.calls.last.request.content) == {"unit_prefs": {"velocity": "in/s"}}
    assert "velocity in/s" in out(capsys)
    assert exits(["me", "set-units", "speed=fast"]).code.startswith("Unknown unit speed")


@respx.mock
def test_production_flip(capsys):
    respx.post(f"{I}/assets/4/production/flip").mock(return_value=httpx.Response(200, json={"state": "off", "last_ping": None}))
    main(["production", "flip", "4"])
    assert "Asset 4 is now off." in out(capsys)
