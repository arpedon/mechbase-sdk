"""CLI: peak tagging + the reading show/delete round trip, offline via respx."""

from __future__ import annotations

import httpx
import respx

from mechbase.cli import main, peaks

READING = {
    "uuid": "u-766", "measurement_point_id": 2, "point_sequence": 766, "data": {"rms": 0.62},
    "status": "warning", "notes": "", "created_at": "2026-11-14T14:02:00Z",
}


def test_peaks_tags_mains_multiples_only():
    freq = [i * 0.5 for i in range(400)]  # 0..199.5 Hz
    amp = [0.0] * 400
    amp[200] = 3.0  # 100 Hz  -> 2×50
    amp[49] = 0.5   # 24.5 Hz -> shaft, untagged
    found = peaks(freq, amp, top=5)
    assert found[0] == {"hz": 100.0, "amplitude": 3.0, "note": "2×50 Hz (electrical)"}
    assert found[1]["hz"] == 24.5 and found[1]["note"] == ""
    # a shaft line one bin off a mains multiple is not electrical
    amp[103] = 1.0  # 51.5 Hz
    assert next(p for p in peaks(freq, amp) if p["hz"] == 51.5)["note"] == ""


@respx.mock
def test_reading_show_and_delete(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("MECHBASE_TOKEN", "tok")
    monkeypatch.setenv("MECHBASE_URL", "https://example.test")
    base = "https://example.test/api/installations/2044"
    respx.get(f"{base}/measurement-points/2/measurements/766/").mock(return_value=httpx.Response(200, json=READING))
    respx.get(f"{base}/analytics/measurements/u-766/spectra/").mock(
        return_value=httpx.Response(200, json={"freq_hz": [0, 50, 100, 150], "velocity": [0, 1, 3, 0]})
    )
    delete = respx.delete(f"{base}/measurement-points/2/measurements/766/").mock(
        return_value=httpx.Response(200, json={"deleted": True, "uuid": "u-766"})
    )

    main(["reading", "show", "-i", "2044", "2", "766"])
    out = capsys.readouterr().out
    assert "WARNING" in out and "2×50 Hz (electrical)" in out

    main(["reading", "delete", "-i", "2044", "-y", "2", "766"])
    assert delete.called


@respx.mock
def test_html_error_page_is_not_dumped(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("MECHBASE_TOKEN", "tok")
    monkeypatch.setenv("MECHBASE_URL", "https://example.test")
    respx.get("https://example.test/api/me/").mock(
        return_value=httpx.Response(503, text="<!DOCTYPE html><html><body>Service Not Available</body></html>")
    )
    try:
        main(["whoami"])
    except SystemExit as e:
        assert str(e.code) == "Error: 503 from https://example.test (server unavailable or not a Mechbase API)"
    else:
        raise AssertionError("expected exit")


@respx.mock
def test_zone_guest_all_asset_type_cli(monkeypatch, tmp_path, capsys):
    import json

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("MECHBASE_TOKEN", "tok")
    monkeypatch.setenv("MECHBASE_URL", "https://example.test")
    monkeypatch.setenv("MECHBASE_INSTALLATION", "7")
    monkeypatch.chdir(tmp_path)
    base = "https://example.test/api/installations/7"
    atype = {"uuid": "t", "code": "QB-STD", "name": "QB", "manufacturer": "", "checklist": [{"title": "Oil"}],
             "asset_count": 0, "document_count": 0}
    respx.get(f"{base}/zones").mock(return_value=httpx.Response(200, json={"items": [
        {"uuid": "a", "zone_id": 1, "name": "A"}, {"uuid": "b", "zone_id": 2, "name": "B"}]}))
    z1 = respx.patch(f"{base}/zones/1").mock(return_value=httpx.Response(200, json={"uuid": "a", "zone_id": 1, "name": "A"}))
    z2 = respx.patch(f"{base}/zones/2").mock(return_value=httpx.Response(200, json={"uuid": "b", "zone_id": 2, "name": "B"}))
    put = respx.put(f"{base}/asset-types").mock(return_value=httpx.Response(200, json=atype))
    asset = respx.patch(f"{base}/assets/5").mock(return_value=httpx.Response(200, json={
        "uuid": "x", "asset_id": 5, "name": "P", "status": 1}))

    main(["zone", "guest", "on", "--all"])
    assert json.loads(z1.calls.last.request.content) == {"guest_view": True} and z2.called
    assert "2 zone(s)" in capsys.readouterr().out

    (tmp_path / "list.json").write_text('[{"title": "Oil", "item_type": "pass_fail"}]')
    main(["asset-type", "checklist", "QB-STD", "list.json"])
    assert json.loads(put.calls.last.request.content) == {"code": "QB-STD", "checklist": [{"title": "Oil", "item_type": "pass_fail"}]}

    main(["asset", "set-type", "QB-STD", "5"])
    assert json.loads(asset.calls.last.request.content) == {"asset_type": "QB-STD"}
    main(["asset", "set-type", "--clear", "5"])
    assert json.loads(asset.calls.last.request.content) == {"asset_type": None}
