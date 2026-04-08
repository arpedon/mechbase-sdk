"""Push a measurement from a maintnode-style Python script.

    MECHBASE_TOKEN=... MECHBASE_URL=http://localhost:8000 python push_measurement.py
"""

from __future__ import annotations

import os

from mechbase import Mechbase


def main() -> None:
    token = os.environ["MECHBASE_TOKEN"]
    base = os.environ.get("MECHBASE_URL", "http://localhost:8000")

    with Mechbase(token=token, base_url=base) as client:
        me = client.me()
        inst = client.for_installation(me.current_installation_id)

        point = inst.measurement_points.list(transducer_type="VB", limit=1)[0]
        print(f"pushing to point {point.point_id} ({point.name})")

        m = inst.measurements.create(
            point_id=point.point_id,
            data={"rms": 2.3, "peak": 4.1},
            notes="from push_measurement.py",
        )
        print(f"ok -> {m.uuid} sequence={m.point_sequence} status={m.status}")


if __name__ == "__main__":
    main()
