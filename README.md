# mechbase-sdk

Official client SDKs for the [Mechbase](https://app.mechbase.io) condition-monitoring platform.

The default base URL is `https://app.mechbase.io`. For self-hosted installations, pass your own base URL to the client constructor.

Four languages, one uniform surface:

| Language | Path        | Package                                   |
|----------|-------------|-------------------------------------------|
| Python   | [`python/`](python/) | `mechbase` (PyPI — tbd)                   |
| Go       | [`go/`](go/)         | `github.com/arpedon/mechbase-sdk/go`      |
| Swift    | [`swift/`](swift/)   | SwiftPM product `Mechbase`                |
| Kotlin   | [`kotlin/`](kotlin/) | `com.arpedon:mechbase-sdk` (Maven — tbd)  |

The canonical API surface is tracked in [`openapi.json`](openapi.json), dumped from the
live mechbase-v2 `NinjaAPI`. All clients are hand-written to match it — no codegen in v1.

## What the SDK lets you do

- **Maintnode / ops scripts (Python, Go):** push measurements, list assets and measurement
  points, poll historical readings.
- **Field survey apps (Swift iOS, Kotlin Android):** start a route execution, submit item
  responses with photos, author new findings on the fly, triage zone-only items to assets.

## Uniform public surface (Python example)

```python
from mechbase import Mechbase

client = Mechbase(token="...")  # defaults to https://app.mechbase.io
# or, for self-hosted:
# client = Mechbase(token="...", base_url="https://mechbase.internal.acme.com")
me = client.me()

inst = client.for_installation(me.current_installation_id)
assets = inst.assets.list(q="pump", limit=50)

# Push a measurement
inst.measurements.create(point_id=42, data={"rms": 2.3}, notes="manual reading")

# Run a route
execution = inst.routes.start(route_uuid="...")
execution.respond(route_item_uuid="...", data={"passed": True})
execution.add_field_item(zone_id=3, label="Oil leak under pump",
                         item_type="pass_fail",
                         data={"passed": False, "severity": "major"})
execution.complete()
```

Go / Swift / Kotlin expose the same shape with idiomatic names
(`client.ForInstallation(id).Assets.List(ctx, …)`, etc.).

## Auth

Bearer tokens. Create one under Mechbase → Settings → API tokens; each token is scoped to
a single user + installation.

## Updating `openapi.json`

Run from a mechbase-v2 checkout:

```bash
python scripts/dump-openapi.py > /path/to/mechbase-sdk/openapi.json
```

## License

MIT — see [LICENSE](LICENSE).
