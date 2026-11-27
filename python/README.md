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
inst.assets.create(name="Box 12", asset_type="QB-STD")   # type by code, one request
inst.zones.set_guest_view(True, zone_ids=[1, 2])         # or section_id=..., or all=True

inst.overview()                                          # the web home: counts, needs attention, running routes
for entry in inst.activity.iter():                       # newest first, follows the cursor
    ...
board = inst.dashboards.get()                            # the default board
board = inst.dashboards.get(etag=board.etag)             # board.not_modified on a 304: keep what you have
inst.measurements.analysis(point_id=2, point_sequence=766)  # waveform, spectra, markers, thermography
inst.routes.execution(run_uuid).amend_answer(item_uuid, {"passed": True}, idempotency_key=key)
```

Every request sends `X-Timezone` (this machine's IANA zone) so the server's "today" (dashboards,
running hours) is yours: `Mechbase(token=..., timezone="Europe/Athens")` overrides it, `""` turns it off.
Retry-safe writes take a client-minted `uuid=` (routes, checks, surveys, photo and document uploads) or an
`idempotency_key=` (measurements, route answers, amendments).

Throttled requests (HTTP 429) are retried up to 6 attempts in total, waiting `Retry-After`
(when sent) or 1, 2, 4... seconds, before raising `MechbaseError`. A wait over 60 s (the API's
burst window is 60 requests a minute) fails at once with the server's message.

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
mechbase devices                     # MaintNodes: online, health warnings, channels, tunnels
mechbase device show "Node A"        # channels by group, factory health URL (staff), remote access
mechbase device rename 6f1e "Boiler room node"
mechbase group set "Node A" hat interval=600
mechbase tunnels                     # remote access you can open (--all: every installation, staff)
mechbase tunnel open logo            # an http tunnel's page in the browser
mechbase tunnel file ssh             # an stcp tunnel's frpc file (staff): frpc -c <file>
mechbase sources 2                   # a point's data sources
mechbase source add 2 source_type=maintnode device=<node uuid> group=<uuid> mn_channel=3 sensor=accelerometer
mechbase source set 2 6f1c sensitivity=50
mechbase source delete 2 6f1c

mechbase overview                    # status counts, needs attention, running routes, back to normal
mechbase alerts                      # every asset needing attention (--silent: the silent ones)
mechbase activity -n 50              # status changes, notes, findings, route runs, by day
mechbase search pump --in points     # counts per category and the matches
mechbase hours --since 2026-11-01    # running hours of production-tracked assets (default today)
mechbase production flip 4           # switch asset 4 running ⇄ stopped now
mechbase dashboards ; mechbase dashboard Boilers   # a board's tiles (no name: your default board)
mechbase reading analysis 2 766      # values, spectrum peaks, bearing markers, shaft order, hot spots
mechbase finding new 2 766 --fault bpfo --severity major --hz 87.3   # no --fault: lists the choices
mechbase bearing search 6205         # or --order 3.58: bearings matching a tone
mechbase runs "Daily round"          # a route's run history
mechbase run report <run uuid>       # totals, non-conformities, unanswered checks
mechbase ncs --asset 4 ; mechbase nc resolve <uuid> --comment "topped up"
mechbase survey new "Walkdown"       # a blank route and its first run
mechbase route new "Night" --check "Oil level" --check "Guard fitted"   # or --file checks.json
mechbase route rename Night "Night shift" ; mechbase route delete "Night shift"
mechbase check add Night "Bearing temp" --type numerical --unit °C
mechbase check mv Night 3 0          # check #3 to the top of its stop ; check rm Night 3
mechbase device lookup <balena uuid> # from the label QR: free, ours or taken
mechbase device claim <balena uuid> --name "Boiler room node"
mechbase device channels "Node A"    # free and used channels per group
mechbase device creds "Node A"       # push the device its credentials again
mechbase notify show ; mechbase notify set notifications_muted=on severity_threshold=3 ; mechbase notify test
mechbase me set-units velocity=in/s temperature=°F
```

Routes take a name or the start of a uuid, and checks their number (`#3`), label or uuid.

Devices, groups and tunnels take a name or the start of a uuid. `source` and `group` fields are
the web form's (`key=value`; plain numbers, `null`, `true` and `false` are sent as JSON, and
`key='"1.50"'` forces a string), and any field left out keeps its value.

Reading numbers are the ones in the web URL (`…/measurementpoints/2/measurements/766/`).
Add `--json` to any command for scripting; `MECHBASE_TOKEN`, `MECHBASE_URL` and
`MECHBASE_INSTALLATION` override the stored config.

For the MaintNode device side use `MaintNode(node_uuid=..., token=<the device's API token>)`: config,
measurements and files need the token, and so do heartbeats once the device is claimed.
`node.heartbeat(config_version=MaintNode.config_version(cfg), hardware={...})` reports what it applied
and detected.

Full docs and the other language SDKs (Go, Swift, Kotlin) live in the
[mechbase-sdk repo](https://github.com/arpedon/mechbase-sdk).
