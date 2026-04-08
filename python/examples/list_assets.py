"""List assets in the current installation."""

from __future__ import annotations

import os

from mechbase import Mechbase


def main() -> None:
    token = os.environ["MECHBASE_TOKEN"]
    base = os.environ.get("MECHBASE_URL", "http://localhost:8000")

    with Mechbase(token=token, base_url=base) as client:
        me = client.me()
        inst = client.for_installation(me.current_installation_id)
        for a in inst.assets.list(limit=100):
            print(f"#{a.asset_id:<4} {a.name:<40} status={a.status} class={a.machine_class}")


if __name__ == "__main__":
    main()
