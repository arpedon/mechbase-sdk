from __future__ import annotations

import hashlib
import json

import httpx
import pytest
import respx

from mechbase import AuthError, MaintNode, ValidationError

BASE = "https://example.test"
YAML = "measurements:\n  - group: hat\nfrp:\n  token: s3cret\n"


@respx.mock
def test_config_sends_device_token_and_returns_the_body_verbatim():
    route = respx.get(f"{BASE}/api/maintnode/node-1/config/").mock(
        return_value=httpx.Response(200, text=YAML, headers={"Content-Type": "application/x-yaml"}))
    node = MaintNode(node_uuid="node-1", token="dev-tok", base_url=BASE)
    cfg = node.config()
    assert cfg == YAML
    assert route.calls.last.request.headers["Authorization"] == "Bearer dev-tok"
    assert MaintNode.config_version(cfg) == hashlib.sha256(YAML.encode()).hexdigest()
    assert MaintNode.config_version(YAML.encode()) == MaintNode.config_version(cfg)


@respx.mock
def test_tokenless_node_sends_no_auth_and_surfaces_the_403():
    route = respx.get(f"{BASE}/api/maintnode/node-1/config/").mock(
        return_value=httpx.Response(403, json={"detail": "Invalid or missing token."}))
    node = MaintNode(node_uuid="node-1", base_url=BASE)
    with pytest.raises(AuthError) as e:
        node.config()
    assert route.calls.last.request.headers.get("Authorization") is None
    assert e.value.status == 403


@respx.mock
def test_push_measurements_authenticated():
    route = respx.post(f"{BASE}/api/maintnode/node-1/measurements/").mock(
        return_value=httpx.Response(200, json=[
            {"mapping_uuid": "map-1", "ok": True, "measurement_uuid": "m-1",
             "local_uuid": "L1", "error": ""}])
    )
    node = MaintNode(node_uuid="node-1", token="dev-tok", base_url=BASE)
    res = node.push_measurements([{"mapping_uuid": "map-1", "data": {"rms": 1.0}}])
    assert res[0].ok is True and res[0].measurement_uuid == "m-1"
    assert route.calls.last.request.headers["Authorization"] == "Bearer dev-tok"
    assert json.loads(route.calls.last.request.content) == {
        "measurements": [{"mapping_uuid": "map-1", "data": {"rms": 1.0}}]
    }


@respx.mock
def test_measurement_file_authenticated():
    route = respx.post(f"{BASE}/api/maintnode/node-1/measurements/m-1/file/").mock(
        return_value=httpx.Response(200, json={"ok": True}))
    MaintNode(node_uuid="node-1", token="dev-tok", base_url=BASE).add_measurement_file("m-1", file=b"\x00\x01")
    assert route.calls.last.request.headers["Authorization"] == "Bearer dev-tok"


@respx.mock
def test_heartbeat_minimal_body_unchanged():
    route = respx.post(f"{BASE}/api/maintnode/node-1/heartbeat/").mock(
        return_value=httpx.Response(200, json={"status": "ok"}))
    MaintNode(node_uuid="node-1", base_url=BASE).heartbeat(balena_uuid="bal-1", services={"agent": "1.2.3"})
    assert json.loads(route.calls.last.request.content) == {"balena_uuid": "bal-1", "services": {"agent": "1.2.3"}}


@respx.mock
def test_heartbeat_reports_config_version_and_hardware():
    route = respx.post(f"{BASE}/api/maintnode/node-1/heartbeat/").mock(
        return_value=httpx.Response(200, json={"status": "ok"}))
    hw = {"hat_addresses": [0, 1], "usb201": False,
          "modbus": [{"host": "10.0.0.5", "port": 502, "unit_id": 1, "reachable": True}]}
    version = MaintNode.config_version(YAML)
    MaintNode(node_uuid="node-1", token="dev-tok", base_url=BASE).heartbeat(config_version=version, hardware=hw)
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer dev-tok"
    assert json.loads(req.content) == {"balena_uuid": "", "services": {}, "config_version": version, "hardware": hw}


@respx.mock
def test_heartbeat_out_of_bounds_is_a_validation_error():
    respx.post(f"{BASE}/api/maintnode/node-1/heartbeat/").mock(
        return_value=httpx.Response(422, json={"detail": "hardware.hat_addresses: too long"}))
    with pytest.raises(ValidationError):
        MaintNode(node_uuid="node-1", token="t", base_url=BASE).heartbeat(hardware={"hat_addresses": list(range(9))})
