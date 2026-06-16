from __future__ import annotations

import httpx
import respx

from mechbase import MaintNode

BASE = "https://example.test"


@respx.mock
def test_config_and_no_auth_header():
    captured = {}

    def _cfg(request):
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json="ssh-key: abc\nfoo: bar\n")

    respx.get(f"{BASE}/api/maintnode/node-1/config/").mock(side_effect=_cfg)
    node = MaintNode(node_uuid="node-1", base_url=BASE)
    cfg = node.config()
    assert cfg.startswith("ssh-key")
    assert captured["auth"] is None  # no bearer token sent


@respx.mock
def test_push_measurements():
    respx.post(f"{BASE}/api/maintnode/node-1/measurements/").mock(
        return_value=httpx.Response(200, json=[
            {"mapping_uuid": "map-1", "ok": True, "measurement_uuid": "m-1",
             "local_uuid": "L1", "error": ""}])
    )
    node = MaintNode(node_uuid="node-1", base_url=BASE)
    res = node.push_measurements([{"mapping_uuid": "map-1", "data": {"rms": 1.0}}])
    assert res[0].ok is True and res[0].measurement_uuid == "m-1"


@respx.mock
def test_heartbeat():
    respx.post(f"{BASE}/api/maintnode/node-1/heartbeat/").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    node = MaintNode(node_uuid="node-1", base_url=BASE)
    out = node.heartbeat(balena_uuid="bal-1", services={"agent": "1.2.3"})
    assert out["ok"] is True
