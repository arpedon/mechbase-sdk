"""Seed the Aeolian Fortune marine demo via the mechbase SDK.

Run after `python manage.py bootstrap_marine` on the target instance:

    MECHBASE_TOKEN=<token> MECHBASE_URL=https://app.mechbase.io \
        python examples/seed_marine.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import random


def healthy_reading(transducer_type: str, rng: random.Random) -> dict:
    if transducer_type == "VB":
        vel = round(rng.uniform(1.0, 2.5), 3)  # mm/s, below ISO minor 2.8
        return {"vel_10hz": vel, "rms": round(rng.uniform(0.3, 0.9), 3),
                "peak": round(rng.uniform(1.0, 2.5), 3), "crest_factor": round(rng.uniform(1.4, 2.2), 2)}
    if transducer_type in ("IR", "TM"):
        return {"value": round(rng.uniform(35.0, 52.0), 1)}
    if transducer_type == "US":
        return {"rms": round(rng.uniform(20.0, 36.0), 1)}
    return {"value": round(rng.uniform(1.0, 10.0), 1)}


def _hotspot(rng: random.Random, severity: int, max_temp: float) -> dict:
    return {"cx_pct": round(rng.uniform(30, 70), 1), "cy_pct": round(rng.uniform(30, 70), 1),
            "max_temp_c": max_temp, "delta_t_c": round(max_temp - rng.uniform(20, 30), 1),
            "severity": severity, "source": "manual"}


def fault_reading(kind: str, rng: random.Random) -> tuple[dict, list[dict] | None]:
    if kind == "vb_minor":
        return ({"vel_10hz": round(rng.uniform(3.2, 4.5), 3), "rms": round(rng.uniform(0.8, 1.4), 3),
                 "peak": round(rng.uniform(3.0, 5.0), 3), "crest_factor": round(rng.uniform(2.5, 3.5), 2)}, None)
    if kind == "ir_minor":
        return ({"value": 72.0}, [_hotspot(rng, 3, 72.0)])
    if kind == "ir_major":
        return ({"value": 96.0}, [_hotspot(rng, 4, 96.0)])
    raise ValueError(f"unknown fault kind {kind!r}")
