# tests/test_seed_marine.py
import random
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "examples"))
import seed_marine as sm  # noqa: E402


def test_healthy_vb_below_iso_minor():
    rng = random.Random(1)
    for _ in range(50):
        data = sm.healthy_reading("VB", rng)
        assert "vel_10hz" in data
        assert data["vel_10hz"] < 2.8  # ISO minor floor


def test_healthy_ir_tm_in_safe_band():
    rng = random.Random(2)
    for ttype, ceiling in (("IR", 65.0), ("TM", 55.0)):
        for _ in range(50):
            assert sm.healthy_reading(ttype, rng)["value"] < ceiling


def test_vb_minor_fault_breaches_minor_not_major():
    rng = random.Random(3)
    data, clusters = sm.fault_reading("vb_minor", rng)
    assert clusters is None
    assert 2.8 < data["vel_10hz"] < 7.1  # Minor band


def test_ir_hotspot_severity_mapping():
    rng = random.Random(4)
    _, minor = sm.fault_reading("ir_minor", rng)
    _, major = sm.fault_reading("ir_major", rng)
    assert minor[0]["severity"] == 3 and major[0]["severity"] == 4
    for c in (minor[0], major[0]):
        assert {"cx_pct", "cy_pct", "max_temp_c", "delta_t_c", "severity"} <= c.keys()
