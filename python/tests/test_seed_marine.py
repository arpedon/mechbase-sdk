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


def test_ir_faults_breach_value_thresholds():
    rng = random.Random(4)
    minor_data, minor_clusters = sm.fault_reading("ir_minor", rng)
    major_data, major_clusters = sm.fault_reading("ir_major", rng)
    assert minor_clusters is None and major_clusters is None
    # IR alarm rule: minor=65, major=90 (°C). Minor band is (65, 90]; Major is > 90.
    assert 65.0 < minor_data["value"] <= 90.0
    assert major_data["value"] > 90.0
