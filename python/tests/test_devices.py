"""Offline tests for devices, tunnels and sources (SDK + CLI)."""
from __future__ import annotations

import json

import httpx
import pytest
import respx

from mechbase import Mechbase
from mechbase.cli import main

BASE = "https://example.test"
I = f"{BASE}/api/installations/2044"
NODE = "6f1e2d3c-4b5a-4968-8776-5a4b3c2d1e0f"
HTTP_T = {"uuid": "aa11-http", "name": "logo", "label": "LOGO", "kind": "http", "staff_only": False,
          "web_url": f"{BASE}/2044/tunnels/aa11-http/", "local_port": None, "visitor_url": None}
STCP_T = {"uuid": "bb22-stcp", "name": "ssh", "label": "SSH", "kind": "stcp", "staff_only": True, "web_url": None,
          "local_port": 22, "visitor_url": f"{BASE}/api/tunnels/bb22-stcp/visitor.toml"}
DEVICE = {"node_uuid": NODE, "name": "Node A", "is_online": True, "last_seen_at": None, "claimed_at": None,
          "health": {}, "health_warnings": ["CPU 95%"], "health_url": None,
          "groups": [{"uuid": "g-1", "name": "hat", "hardware_type": "hat", "hardware_config": {}, "interval": 600,
                      "sample_rate": None, "samples": None,
                      "channels": [{"uuid": "m-1", "channel": 3, "point_id": 1, "point_name": "DE", "asset_id": 1,
                                    "asset_name": "Pump", "sensor": "accelerometer", "last_seen_at": None,
                                    "stale_since": None, "state": "waiting"}]}],
          "tunnels": [HTTP_T, STCP_T]}
SOURCE = {"uuid": "m-1abc", "source_type": "maintnode", "device_id": NODE, "device_name": "Node A",
          "group": {"uuid": "g-1", "name": "hat", "hardware_type": "hat"}, "channel": 3, "sensor": "accelerometer",
          "sensor_config": {"sensitivity": 100.0}, "is_active": True, "last_seen_at": None, "stale_since": None}


@pytest.fixture
def client():
    c = Mechbase(token="tok", base_url=BASE)
    yield c
    c.close()


@pytest.fixture
def cli_env(monkeypatch, tmp_path):
    for k, v in {"XDG_CONFIG_HOME": str(tmp_path), "MECHBASE_TOKEN": "tok", "MECHBASE_URL": BASE,
                 "MECHBASE_INSTALLATION": "2044"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.chdir(tmp_path)


@respx.mock
def test_devices_and_groups(client):
    inst = client.for_installation(2044)
    respx.get(f"{I}/devices").mock(return_value=httpx.Response(200, json=[DEVICE]))
    assert inst.devices.list()[0]["name"] == "Node A"
    rename = respx.patch(f"{I}/devices/{NODE}").mock(return_value=httpx.Response(200, json=DEVICE))
    inst.devices.rename(NODE, "Boiler")
    assert json.loads(rename.calls.last.request.content) == {"name": "Boiler"}
    group = respx.patch(f"{I}/devices/{NODE}/groups/g-1").mock(return_value=httpx.Response(200, json=DEVICE))
    inst.devices.update_group(NODE, "g-1", interval=120)
    assert json.loads(group.calls.last.request.content) == {"interval": 120}


@respx.mock
def test_sources_round_trip(client):
    inst = client.for_installation(2044)
    respx.get(f"{I}/measurement-points/1/sources").mock(return_value=httpx.Response(200, json=[SOURCE]))
    assert inst.sources.list(1)[0]["channel"] == 3
    create = respx.post(f"{I}/measurement-points/1/sources").mock(return_value=httpx.Response(201, json=SOURCE))
    inst.sources.create(1, source_type="mqtt", mqtt_device_id="SN-1")
    assert json.loads(create.calls.last.request.content) == {"source_type": "mqtt", "mqtt_device_id": "SN-1"}
    respx.patch(f"{I}/measurement-points/1/sources/m-1abc").mock(return_value=httpx.Response(200, json=SOURCE))
    inst.sources.update(1, "m-1abc", sensitivity=50)
    respx.delete(f"{I}/measurement-points/1/sources/m-1abc").mock(return_value=httpx.Response(204))
    assert inst.sources.delete(1, "m-1abc") is None


@respx.mock
def test_staff_tunnels(client):
    respx.get(f"{BASE}/api/tunnels").mock(return_value=httpx.Response(200, json=[STCP_T]))
    assert client.tunnels.list()[0]["kind"] == "stcp"
    respx.get(f"{BASE}/api/tunnels/bb22-stcp/visitor.toml").mock(
        return_value=httpx.Response(200, content=b'serverAddr = "frp"\n', headers={"content-type": "application/toml"}))
    assert client.tunnels.visitor_toml("bb22-stcp") == b'serverAddr = "frp"\n'


@respx.mock
def test_cli_devices_show_and_tunnel_file(cli_env, capsys, tmp_path):
    respx.get(f"{I}/devices").mock(return_value=httpx.Response(200, json=[DEVICE]))
    main(["devices"])
    out = capsys.readouterr().out
    assert "Node A" in out and "CPU 95%" in out
    main(["device", "show", "node a"])
    out = capsys.readouterr().out
    assert "CH3" in out and "1 Pump · DE" in out and HTTP_T["web_url"] in out
    respx.get(f"{BASE}/api/tunnels/bb22-stcp/visitor.toml").mock(return_value=httpx.Response(200, content=b"toml"))
    main(["tunnel", "file", "ssh"])
    assert (tmp_path / "Node-A-ssh.toml").read_bytes() == b"toml"
    assert "127.0.0.1:22" in capsys.readouterr().out


@respx.mock
def test_cli_tunnel_open_launches_browser(cli_env, capsys, monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    respx.get(f"{I}/devices").mock(return_value=httpx.Response(200, json=[DEVICE]))
    main(["tunnel", "open", "aa11"])
    assert opened == [HTTP_T["web_url"]]


@respx.mock
def test_cli_source_add_parses_values(cli_env, capsys):
    create = respx.post(f"{I}/measurement-points/1/sources").mock(return_value=httpx.Response(201, json=SOURCE))
    main(["source", "add", "1", "source_type=maintnode", f"device={NODE}", "mn_channel=3", "sensor_min=null"])
    assert json.loads(create.calls.last.request.content) == {
        "source_type": "maintnode", "device": NODE, "mn_channel": 3, "sensor_min": None}
    with pytest.raises(SystemExit):
        main(["source", "add", "1", "oops"])


@respx.mock
def test_cli_source_delete_by_prefix(cli_env, capsys):
    respx.get(f"{I}/measurement-points/1/sources").mock(return_value=httpx.Response(200, json=[SOURCE]))
    delete = respx.delete(f"{I}/measurement-points/1/sources/m-1abc").mock(return_value=httpx.Response(204))
    main(["source", "delete", "1", "m-1", "-y"])
    assert delete.called
