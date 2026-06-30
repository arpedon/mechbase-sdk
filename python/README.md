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

For edge agents identified by a `node_uuid` rather than a bearer token, use `MaintNode`.

Full docs and the other language SDKs (Go, Swift, Kotlin) live in the
[mechbase-sdk repo](https://github.com/arpedon/mechbase-sdk).
