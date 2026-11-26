# mechbase

Official Python client for the [Mechbase](https://app.mechbase.io) condition-monitoring API.

```bash
pip install mechbase
```

```python
from mechbase import Mechbase

client = Mechbase(token="...")  # defaults to https://app.mechbase.io
# self-hosted: Mechbase(token="...", base_url="https://mechbase.internal.acme.com")

me = client.me()
inst = client.for_installation(me.current_installation_id)

assets = inst.assets.list(q="pump", limit=50)
inst.measurements.create(point_id=42, data={"rms": 2.3}, notes="manual reading")
```

## Command line

The package installs a `mechbase` command:

```bash
pipx install mechbase
mechbase login                       # once; token stored in ~/.config/mechbase/config.json
mechbase points --asset 1
mechbase readings 2                  # latest readings of point 2
mechbase reading show 2 766          # values, state and top spectrum peaks (electrical lines tagged)
mechbase reading delete 2 767
mechbase point show 2                # running, stale, alarm limits, last 7 days
mechbase findings --status open      # diagnosed faults
mechbase finding ack <uuid> --wo WO-1234
mechbase finding close <uuid>
mechbase export measurements --point 2 -o readings.csv   # also events, inspections; --format parquet
mechbase photo add point 2 pump.jpg  # or: photo add asset 1 …, photo delete point 2 <uuid>
mechbase logout                      # revokes the stored token
mechbase comments 1                  # an asset's thread
mechbase comment add 1 "Bearing noise after restart" --point 2 --reading 766
mechbase docs 1                      # an asset's documents
mechbase doc add 1 manual.pdf --kind manual
mechbase zone guest on --all                       # QR guest view for zones (or give zone ids)
mechbase asset-type list
mechbase asset-type set QB-STD --name "QB pump"
mechbase asset-type checklist QB-STD list.json     # replaces the type's checklist
mechbase asset-type doc add QB-STD manual.pdf --kind manual
mechbase asset set-type QB-STD 1 2 3               # or: asset set-type --clear 1 2 3
mechbase alarms 2                    # a point's limits: its own, then the installation default
mechbase alarm set 2 --minor 2.8 --major 7.1
mechbase alarm clear 2               # back to the installation default
```

Reading numbers are the ones in the web URL (`…/measurementpoints/2/measurements/766/`).
Add `--json` to any command for scripting; `MECHBASE_TOKEN`, `MECHBASE_URL` and
`MECHBASE_INSTALLATION` override the stored config.

For edge agents identified by a `node_uuid` rather than a bearer token, use `MaintNode`.

Full docs and the other language SDKs (Go, Swift, Kotlin) live in the
[mechbase-sdk repo](https://github.com/arpedon/mechbase-sdk).
