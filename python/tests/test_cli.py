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
