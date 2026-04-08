"""Run a field survey — start an execution, author items on the fly, complete.

Mirrors the Android/iOS survey flow so the same API shape can be exercised
end-to-end from Python.
"""

from __future__ import annotations

import os
import sys

from mechbase import Mechbase


def main() -> None:
    token = os.environ["MECHBASE_TOKEN"]
    base = os.environ.get("MECHBASE_URL", "http://localhost:8000")
    route_uuid = sys.argv[1] if len(sys.argv) > 1 else os.environ["ROUTE_UUID"]

    with Mechbase(token=token, base_url=base) as client:
        me = client.me()
        inst = client.for_installation(me.current_installation_id)

        execution = inst.routes.start(route_uuid)
        print(f"started execution {execution.uuid}")

        first_asset = inst.assets.list(limit=1)[0]

        resp = execution.add_field_item(
            label="Oil leak under pump",
            item_type="pass_fail",
            asset_id=first_asset.asset_id,
            data={"passed": False, "severity": "major"},
            notes="under coupling",
        )
        print(f"added field item -> response {resp.uuid} status={resp.status}")

        final = execution.complete()
        print(f"completed at {final.completed_at}")


if __name__ == "__main__":
    main()
