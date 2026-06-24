"""Standalone SDK example: drive the full client flow against a Mechbase instance.

This demonstrates the end-to-end client path — discover the structure, batch-push
manual point readings (with a couple of curated faults), and run + complete one
execution of each route — using only the public ``mechbase`` SDK surface.

NOTE: the Aeolian Fortune demo itself is now seeded entirely by mechbase-web's
``python manage.py bootstrap_marine`` command (structure + measurements + route
executions, via the ORM). This script is kept as a reusable SDK example; pointed
at an installation that bootstrap_marine created, it will push additional readings
and route runs through the live API.

    MECHBASE_TOKEN=<token> MECHBASE_URL=https://app.mechbase.io \
        python examples/seed_marine.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import random


def healthy_reading(transducer_type: str, rng: random.Random) -> dict:
    if transducer_type == "VB":
        # mm/s. Must stay below the LOWEST ISO 10816 minor threshold across the
        # machine classes in the demo — Class I is 1.8 mm/s — so healthy readings
        # on small (Class I) machines don't falsely trip Minor. Keep margin: <1.5.
        vel = round(rng.uniform(0.4, 1.4), 3)
        return {"vel_10hz": vel, "rms": round(rng.uniform(0.3, 0.9), 3),
                "peak": round(rng.uniform(0.8, 1.6), 3), "crest_factor": round(rng.uniform(1.4, 2.2), 2)}
    if transducer_type in ("IR", "TM"):
        return {"value": round(rng.uniform(35.0, 52.0), 1)}
    if transducer_type == "US":
        return {"rms": round(rng.uniform(20.0, 36.0), 1)}
    return {"value": round(rng.uniform(1.0, 10.0), 1)}


def fault_reading(kind: str, rng: random.Random) -> tuple[dict, list[dict] | None]:
    if kind == "vb_minor":
        return ({"vel_10hz": round(rng.uniform(3.2, 4.5), 3), "rms": round(rng.uniform(0.8, 1.4), 3),
                 "peak": round(rng.uniform(3.0, 5.0), 3), "crest_factor": round(rng.uniform(2.5, 3.5), 2)}, None)
    if kind == "ir_minor":
        return ({"value": round(rng.uniform(68.0, 85.0), 1)}, None)
    if kind == "ir_major":
        return ({"value": round(rng.uniform(92.0, 105.0), 1)}, None)
    raise ValueError(f"unknown fault kind {kind!r}")


from mechbase import Mechbase  # noqa: E402

INSTALLATION_NAME = "Aeolian Fortune"
# Mirror of mechbase-web measurements.marine_demo.MARINE_FAULTS.
FAULTS = {"AF-SWP2-PDE": "vb_minor", "AF-MSB-BRK": "ir_major", "AF-FOT-IRM": "ir_minor"}
N_READINGS = 8           # readings per point (weekly cadence, ~60 days)
DAY_STEP = 7


def _iso_days_ago(n: int) -> str:
    # Lazy import keeps the pure-function tests free of datetime determinism issues.
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


def seed_measurements(inst, points, rng, *, dry_run: bool) -> int:
    items = []
    for p in points:
        if p.transducer_type == "PR":
            continue
        fault = FAULTS.get(p.external_id or "")
        for i in range(N_READINGS):
            days_ago = (N_READINGS - 1 - i) * DAY_STEP
            recent = i >= N_READINGS - 2          # fault ramps on the last 2 readings
            if fault and recent:
                data, _ = fault_reading(fault, rng)
            else:
                data = healthy_reading(p.transducer_type, rng)
            item = {"measurement_point_external_id": p.external_id, "data": data,
                    "timestamp": _iso_days_ago(days_ago),
                    "external_id": f"{p.external_id}-{i}"}
            items.append(item)
    if dry_run:
        print(f"[dry-run] would push {len(items)} readings")
        return len(items)
    # The batch endpoint caps at 1000 items per request; chunk to stay under it.
    chunk = 500
    created = duplicates = errors = 0
    for start in range(0, len(items), chunk):
        result = inst.measurements.create_batch(items[start : start + chunk])
        created += result.created
        duplicates += result.duplicates
        errors += result.errors
    print(f"readings: created={created} duplicates={duplicates} errors={errors}")
    return created


def run_routes(inst, points_by_id, rng, *, dry_run: bool) -> int:
    done = 0
    for route in inst.routes.list(limit=50):
        detail = inst.routes.get(route.uuid)        # dict: {..., "items": [...]}
        if dry_run:
            print(f"[dry-run] would run '{route.name}' ({len(detail['items'])} items)")
            done += 1
            continue
        execution = inst.routes.start(route.uuid)
        for item in detail["items"]:
            data = _response_for(item, points_by_id, rng)
            execution.respond(route_item_uuid=item["uuid"], data=data)
        execution.complete()
        done += 1
        print(f"completed execution of '{route.name}'")
    return done


def _response_for(item: dict, points_by_id: dict, rng: random.Random) -> dict:
    it = item["item_type"]
    if it == "pass_fail":
        passed = rng.random() > 0.1
        return {"passed": passed} if passed else {"passed": False, "severity": "minor"}
    if it == "numerical":
        unit = (item.get("config") or {}).get("unit", "")
        rng_map = {"°C": (20, 60), "bar": (2, 8)}
        lo, hi = rng_map.get(unit, (0.5, 100))
        return {"value": round(rng.uniform(lo, hi), 1)}
    if it == "multi_check":
        return {"results": [{"label": c["label"], "passed": True}
                            for c in (item.get("config") or {}).get("checks", [])]}
    if it == "measurement":
        pt = points_by_id.get(item.get("measurement_point_id"))
        ttype = pt.transducer_type if pt else "TM"
        return healthy_reading(ttype, rng)
    return {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = os.environ["MECHBASE_TOKEN"]
    base = os.environ.get("MECHBASE_URL", "https://app.mechbase.io")
    rng = random.Random(2014)

    with Mechbase(token=token, base_url=base) as client:
        me = client.me()
        inst = client.for_installation(me.current_installation_id)
        names = {i.installation_id: i.name for i in me.installations}
        if names.get(me.current_installation_id) != INSTALLATION_NAME:
            raise SystemExit(
                f"Refusing to seed: token resolves to '{names.get(me.current_installation_id)}', "
                f"not '{INSTALLATION_NAME}'. Use the token printed by bootstrap_marine.")

        points = []
        offset = 0
        while True:
            page = inst.measurement_points.list(limit=100, offset=offset)
            points.extend(page)
            if len(page) < 100:
                break
            offset += 100
        points_by_id = {p.point_id: p for p in points}

        n = seed_measurements(inst, points, rng, dry_run=args.dry_run)
        r = run_routes(inst, points_by_id, rng, dry_run=args.dry_run)
        print(f"Done: {n} readings, {r} route executions on '{INSTALLATION_NAME}' ({base}).")


if __name__ == "__main__":
    main()
