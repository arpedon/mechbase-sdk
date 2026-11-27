"""CLI: peak tagging + the reading show/delete round trip, offline via respx."""

from __future__ import annotations

import json

import httpx
import pytest
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
    gv = respx.post(f"{base}/zones/guest-view").mock(return_value=httpx.Response(200, json={"updated": 2}))
    put = respx.put(f"{base}/asset-types").mock(return_value=httpx.Response(200, json=atype))
    asset = respx.patch(f"{base}/assets/5").mock(return_value=httpx.Response(200, json={
        "uuid": "x", "asset_id": 5, "name": "P", "status": 1}))

    main(["zone", "guest", "on", "--all"])
    assert gv.call_count == 1 and json.loads(gv.calls.last.request.content) == {"enabled": True, "all": True}
    assert "2 zone(s)" in capsys.readouterr().out
    main(["zone", "guest", "off", "--all", "--json"])
    assert json.loads(capsys.readouterr().out) == {"zones": None, "updated": 2, "guest_view": False}
    main(["zone", "guest", "on", "1", "2", "--json"])
    assert json.loads(capsys.readouterr().out)["zones"] == [1, 2]
    assert json.loads(gv.calls.last.request.content) == {"enabled": True, "zone_ids": [1, 2]}

    (tmp_path / "list.json").write_text('[{"title": "Oil", "item_type": "pass_fail"}]')
    patch = respx.patch(f"{base}/asset-types/QB-STD").mock(return_value=httpx.Response(200, json=atype))
    main(["asset-type", "checklist", "QB-STD", "list.json"])
    assert json.loads(patch.calls.last.request.content) == {"checklist": [{"title": "Oil", "item_type": "pass_fail"}]}
    assert not put.called  # a mistyped code must not create a type

    main(["asset", "set-type", "QB-STD", "5"])
    assert json.loads(asset.calls.last.request.content) == {"asset_type": "QB-STD"}
    main(["asset", "set-type", "--clear", "5"])
    assert json.loads(asset.calls.last.request.content) == {"asset_type": None}


@respx.mock
def test_cli_asset_type_typos_and_partial_set_type(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("MECHBASE_TOKEN", "tok")
    monkeypatch.setenv("MECHBASE_URL", "https://example.test")
    monkeypatch.setenv("MECHBASE_INSTALLATION", "7")
    monkeypatch.chdir(tmp_path)
    base = "https://example.test/api/installations/7"
    missing = httpx.Response(404, json={"detail": "Not found."})
    respx.get(f"{base}/asset-types/QB-SDT").mock(return_value=missing)
    respx.patch(f"{base}/asset-types/QB-SDT").mock(return_value=missing)
    put = respx.put(f"{base}/asset-types")
    (tmp_path / "list.json").write_text("[]")

    with pytest.raises(SystemExit) as e:
        main(["asset-type", "set", "QB-SDT"])
    assert "give --name" in str(e.value.code) and not put.called
    with pytest.raises(SystemExit):
        main(["asset-type", "checklist", "QB-SDT", "list.json"])
    assert not put.called

    respx.patch(f"{base}/assets/5").mock(return_value=httpx.Response(200, json={"uuid": "x", "asset_id": 5, "name": "P", "status": 1}))
    respx.patch(f"{base}/assets/999").mock(return_value=missing)
    respx.patch(f"{base}/assets/6").mock(return_value=httpx.Response(200, json={"uuid": "y", "asset_id": 6, "name": "Q", "status": 1}))
    with pytest.raises(SystemExit) as e:
        main(["asset", "set-type", "QB-STD", "5", "999", "6"])
    out = capsys.readouterr()
    assert e.value.code == 1 and "2 asset(s): 5, 6." in out.out and "Asset 999 not changed: 404" in out.err


def test_config_path_follows_xdg_set_after_import(monkeypatch, tmp_path, capsys):
    # The CLI is imported before this test sets the variable: the write must still land here.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    main(["use", "5"])
    assert json.loads((tmp_path / "mechbase" / "config.json").read_text())["installation"] == 5
