# mechbase-sdk

[![Kotlin](https://img.shields.io/maven-central/v/com.arpedon/mechbase-sdk?label=Kotlin&logo=kotlin&color=blue)](https://central.sonatype.com/artifact/com.arpedon/mechbase-sdk)
[![Python](https://img.shields.io/pypi/v/mechbase?label=Python&logo=python&logoColor=white&color=blue)](https://pypi.org/project/mechbase/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Official client SDKs for the [Mechbase](https://app.mechbase.io) condition-monitoring platform.

The default base URL is `https://app.mechbase.io`. For self-hosted installations, pass your own base URL to the client constructor.

Four languages, one uniform surface:

| Language | Path        | Install                                                              |
|----------|-------------|---------------------------------------------------------------------|
| Python   | [`python/`](python/) | `pip install mechbase`                                      |
| Go       | [`go/`](go/)         | `go get github.com/arpedon/mechbase-sdk/go`                 |
| Swift    | [`swift/`](swift/)   | `.package(url: "https://github.com/arpedon/mechbase-sdk", from: "0.2.0")` |
| Kotlin   | [`kotlin/`](kotlin/) | `implementation("com.arpedon:mechbase-sdk:0.2.2")`          |

How each SDK is published (and how to cut a release) is documented in
[`RELEASING.md`](RELEASING.md).

The canonical API surface is tracked in [`openapi.json`](openapi.json), dumped from the
live mechbase-web `NinjaAPI`. All clients are hand-written to match it — no codegen in v1.

## What the SDK lets you do

- **Maintnode / ops scripts (Python, Go):** push measurements, list assets and measurement
  points, poll historical readings.
- **Registry sync (all languages):** create, upsert, update, and delete assets,
  measurement-points, sections, and zones — all addressable by `external_id`, so you can
  mirror a registry from a CMMS or ERP without managing numeric IDs.
- **Batch measurement push (all languages):** send many readings in a single request via
  `create_batch` / `CreateBatch`; the response reports created, duplicate, and error counts
  per item.
- **Field survey apps (Swift iOS, Kotlin Android):** start a route execution, submit item
  responses with photos, author new findings on the fly, triage zone-only items to assets.

A **maintnode device client** (`MaintNode` in Python, `NewMaintNode` in Go) is available
for edge agents that are identified by a `node_uuid` rather than a bearer token.

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

### Registry sync + batch push (Python)

```python
from mechbase import Mechbase

client = Mechbase(token="...")
inst = client.for_installation(client.me().current_installation_id)

# Upsert the hierarchy by external_id — safe to run repeatedly
inst.sections.upsert(external_id="HALL-A", name="Hall A")
inst.zones.upsert(external_id="Z-1", name="Pump Row", section_external_id="HALL-A")
inst.assets.upsert(external_id="PUMP-1", name="Feed Pump 1",
                   zone_external_id="Z-1", equipment_type="pump", machine_class="II")
inst.measurement_points.upsert(external_id="PUMP-1-DE", name="Drive End",
                               asset_external_id="PUMP-1", transducer_type="accel",
                               measurement_unit_code="mm_s")

# Push readings in bulk
result = inst.measurements.create_batch([
    {"measurement_point_external_id": "PUMP-1-DE", "data": {"rms": 2.3}, "external_id": "r-1"},
])
print(f"created={result.created} duplicates={result.duplicates} errors={result.errors}")
```

## Auth

Bearer tokens. Create one under Mechbase → Settings → API tokens; each token is scoped to
a single user + installation.

## Updating `openapi.json`

Run from a mechbase-web checkout:

```bash
python scripts/dump-openapi.py > /path/to/mechbase-sdk/openapi.json
```

## License

MIT — see [LICENSE](LICENSE).
