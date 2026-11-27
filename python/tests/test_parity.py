"""Offline tests for findings, exports, photos, context, cancel, hotspots, revoke and the new CLI commands."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from mechbase import ConflictError, Mechbase
from mechbase.cli import main

BASE = "https://example.test"
I = f"{BASE}/api/installations/2044"
FINDING = {
    "uuid": "f-1", "status": "open", "fault_type": "misalignment", "fault_type_display": "Misalignment",
    "severity": "major", "recommended_action": "Realign", "comment": "", "evidence": {}, "work_order_ref": "",
    "created_at": "2026-11-20T08:00:00Z", "updated_at": "2026-11-20T08:00:00Z", "asset_id": 1,
    "asset_name": "Pump 1", "point_id": 2, "point_name": "DE", "point_location": "", "web_url": "/x",
}
POINT = {"uuid": "p", "point_id": 2, "name": "DE", "asset_id": 1, "transducer_type": "VIB",
         "measurement_unit_code": "mm/s", "location": "", "status": 2,
         "photos": [{"uuid": "ph-1", "url": "https://x/1.jpg"}], "reference_photo_uuid": "ph-1",
         "display_units": {"velocity": {"native": "mm/s", "unit": "in/s", "scale": 0.03937, "offset": 0}}}
FILE = {"uuid": "ph-2", "name": "a.jpg", "kind": "image", "file_url": "https://x/2.jpg", "created_at": "2026-11-20T08:00:00Z"}
EXEC = {"uuid": "e-1", "route_uuid": "r", "status": "cancelled", "started_at": None, "completed_at": None, "session_id": "s"}


@pytest.fixture
def inst():
    c = Mechbase(token="tok", base_url=BASE)
    yield c.for_installation(2044)
    c.close()


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("MECHBASE_TOKEN", "tok")
    monkeypatch.setenv("MECHBASE_URL", BASE)
    monkeypatch.setenv("MECHBASE_INSTALLATION", "2044")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@respx.mock
def test_findings_list_and_acknowledge(inst):
    lst = respx.get(f"{I}/findings/").mock(side_effect=[
        httpx.Response(200, json={"items": [FINDING], "next_cursor": "c2"}),
        httpx.Response(200, json={"items": [{**FINDING, "uuid": "f-2"}], "next_cursor": None}),
    ])
    ack = respx.post(f"{I}/findings/f-1/status/").mock(
        return_value=httpx.Response(200, json={**FINDING, "status": "acknowledged", "work_order_ref": "WO-9"}))
    f, f2 = inst.findings.list(status="open", asset_id=1)
    assert f.fault_type_display == "Misalignment" and f.extra["evidence"] == {} and f2.uuid == "f-2"
    assert dict(lst.calls.last.request.url.params) == {"status": "open", "asset_id": "1", "limit": "50", "cursor": "c2"}
    f = inst.findings.acknowledge("f-1", work_order_ref="WO-9")
    assert json.loads(ack.calls.last.request.content) == {"status": "acknowledged", "work_order_ref": "WO-9"}
    assert f.status == "acknowledged"


@respx.mock
def test_point_photos_reference_context(inst):
    up = respx.post(f"{I}/measurement-points/2/photos/").mock(return_value=httpx.Response(201, json=FILE))
    respx.delete(f"{I}/measurement-points/2/photos/ph-1").mock(return_value=httpx.Response(204))
    ref = respx.put(f"{I}/measurement-points/2/reference-photo").mock(return_value=httpx.Response(200, json=POINT))
    respx.get(f"{I}/measurement-points/2/context").mock(return_value=httpx.Response(200, json={"data_key": "rms", "unit": "mm/s", "week": []}))

    assert inst.measurement_points.add_photo(2, b"jpg", uuid="ph-2").uuid == "ph-2"
    body = up.calls.last.request.content
    assert b'name="keep_reference"\r\n\r\ntrue' in body and b'name="uuid"\r\n\r\nph-2' in body
    assert inst.measurement_points.delete_photo(2, "ph-1") is None
    p = inst.measurement_points.set_reference_photo(2, "ph-1")
    assert json.loads(ref.calls.last.request.content) == {"uuid": "ph-1"}
    assert p.reference_photo_uuid == "ph-1" and p.photos[0].url == "https://x/1.jpg"
    assert p.display_units["velocity"]["unit"] == "in/s"
    assert inst.measurement_points.context(2)["data_key"] == "rms"


@respx.mock
def test_cancel_conflict_hotspots_redirects_revoke(inst):
    respx.post(f"{I}/executions/e-1/cancel").mock(side_effect=[httpx.Response(200, json=EXEC), httpx.Response(409, json={"detail": "has answers"})])
    assert inst.routes.execution("e-1").cancel().status == "cancelled"
    with pytest.raises(ConflictError):
        inst.routes.execution("e-1").cancel()
    hs = respx.patch(f"{I}/measurements/m-1/hotspots/").mock(return_value=httpx.Response(200, json={
        "uuid": "m-1", "measurement_point_id": 2, "point_sequence": 1, "data": {}, "status": "ok", "created_at": "t"}))
    inst.measurements.set_hotspots("m-1", [{"x": 1, "y": 2, "t": 80.0}])
    assert json.loads(hs.calls.last.request.content) == {"hot_clusters": [{"x": 1, "y": 2, "t": 80.0}]}
    respx.get(f"{I}/legacy-redirects").mock(return_value=httpx.Response(200, json={"items": [{"legacy_url": "/old"}], "total": 1}))
    assert inst.legacy_redirects() == [{"legacy_url": "/old"}]
    rv = respx.post(f"{BASE}/api/auth/token/revoke").mock(return_value=httpx.Response(200, json={"ok": True}))
    Mechbase(token="tok", base_url=BASE).revoke_token()
    assert rv.called


@respx.mock
def test_cli_export_polls_then_writes_file(cli_env, capsys):
    done = {"job_uuid": "j", "dataset": "measurements", "file_format": "csv", "state": "done", "row_count": 3,
            "download_url": "http://internal-host/api/x/download/?sig=abc", "created_at": "t"}
    create = respx.post(f"{I}/analytics/exports/").mock(return_value=httpx.Response(202, json={"job_uuid": "j", "state": "pending", "status_url": "/s"}))
    respx.get(f"{I}/analytics/exports/j/").mock(return_value=httpx.Response(200, json=done))
    dl = respx.get(f"{I}/analytics/exports/j/download/", params={"sig": "abc"}).mock(return_value=httpx.Response(200, content=b"a,b\n1,2\n"))
    main(["export", "measurements", "--point", "2", "--since", "2026-01-01T00:00:00+00:00", "-o", "out.csv"])
    assert dl.called
    assert json.loads(create.calls.last.request.content)["filters"] == {"point_id": 2, "created_from": "2026-01-01T00:00:00+00:00"}
    with pytest.raises(SystemExit, match="only filter the measurements"):
        main(["export", "events", "--point", "2"])
    assert (cli_env / "out.csv").read_bytes() == b"a,b\n1,2\n"
    assert "Wrote 3 rows" in capsys.readouterr().out


@respx.mock
def test_cli_findings_point_show_logout(cli_env, capsys):
    respx.get(f"{I}/findings/").mock(return_value=httpx.Response(200, json={"items": [FINDING]}))
    respx.get(f"{I}/measurement-points/2").mock(return_value=httpx.Response(200, json=POINT))
    respx.get(f"{I}/measurement-points/2/context").mock(return_value=httpx.Response(200, json={
        "data_key": "rms", "unit": "mm/s", "running": True, "running_at": "2026-11-26T06:00:00Z",
        "limits": {"minor": 2.8, "major": 7.1}, "week": [{"t": "a", "v": 1.0}, {"t": "b", "v": 2.5}]}))
    rv = respx.post(f"{BASE}/api/auth/token/revoke").mock(return_value=httpx.Response(200, json={"ok": True}))

    main(["findings", "--status", "open"])
    assert "Misalignment" in capsys.readouterr().out
    main(["point", "show", "2"])
    out = capsys.readouterr().out
    assert "running" in out and "minor 2.8 · major 7.1" in out and "last 2.5" in out
    (cli_env / "mechbase").mkdir()
    (cli_env / "mechbase" / "config.json").write_text(json.dumps({"token": "stored", "url": BASE}))
    main(["logout"])
    out = capsys.readouterr()
    # logout revokes the stored token it forgets, not the MECHBASE_TOKEN override
    assert rv.calls.last.request.headers["Authorization"].endswith("stored") and "Signed out." in out.out
    assert "MECHBASE_TOKEN is still set" in out.err
    assert json.loads((cli_env / "mechbase" / "config.json").read_text()) == {"url": BASE}
    main(["point", "show", "--json", "2"])
    assert json.loads(capsys.readouterr().out)["photos"] == [{"uuid": "ph-1", "url": "https://x/1.jpg"}]
