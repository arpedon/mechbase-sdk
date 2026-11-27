from __future__ import annotations

from ._base import InstallationScoped


class Devices(InstallationScoped):
    """The installation's MaintNode devices: state, health, groups, channels and tunnels."""

    def list(self) -> list[dict]:
        """Devices needing attention first. Each: node_uuid, name, is_online, last_seen_at, claimed_at,
        health, health_warnings, health_url (staff), groups[{uuid, name, hardware_type, hardware_config,
        interval, sample_rate, samples, channels[{uuid, channel, point_id, point_name, asset_id,
        asset_name, sensor, last_seen_at, stale_since, state}]}], tunnels[{uuid, name, label, kind,
        staff_only, web_url, local_port, visitor_url}] (the ones you may open)."""
        return self._http.request("GET", self._path("/devices"))

    def get(self, node_uuid: str) -> dict:
        return self._http.request("GET", self._path(f"/devices/{node_uuid}"))

    def rename(self, node_uuid: str, name: str) -> dict:
        return self._http.request("PATCH", self._path(f"/devices/{node_uuid}"), json={"name": name})

    def update_group(self, node_uuid: str, group_uuid: str, **fields) -> dict:
        """The group edit page's fields (name, interval, sample_rate, samples, hardware_id,
        hardware_address, Modbus connection fields); unsent ones keep their value. Returns the device."""
        return self._http.request("PATCH", self._path(f"/devices/{node_uuid}/groups/{group_uuid}"), json=fields)


class Sources(InstallationScoped):
    """A point's data sources (MQTT or MaintNode channels). Fields are the add-source page's,
    e.g. source_type="maintnode", device=<node uuid>, group=<uuid> or group_name + hardware_type,
    mn_channel (or register_address for Modbus), sensor, sensitivity, sensor_min, sensor_max …"""

    def list(self, point_id: int) -> list[dict]:
        """Each: uuid, source_type, device_id, device_name, group{uuid, name, hardware_type}, channel,
        sensor, sensor_config, is_active, last_seen_at, stale_since."""
        return self._http.request("GET", self._path(f"/measurement-points/{point_id}/sources"))

    def create(self, point_id: int, **fields) -> dict:
        """A MaintNode source with no `group` creates one. Omitted fields take the page's defaults."""
        return self._http.request("POST", self._path(f"/measurement-points/{point_id}/sources"), json=fields)

    def update(self, point_id: int, source_uuid: str, **fields) -> dict:
        """Unsent fields keep their value; type, device and group stay."""
        return self._http.request("PATCH", self._path(f"/measurement-points/{point_id}/sources/{source_uuid}"),
                                  json=fields)

    def delete(self, point_id: int, source_uuid: str) -> None:
        self._http.request("DELETE", self._path(f"/measurement-points/{point_id}/sources/{source_uuid}"))


class Tunnels:
    """Every device's tunnels across installations (staff only)."""

    def __init__(self, http):
        self._http = http

    def list(self) -> list[dict]:
        """Each tunnel plus installation_id, installation_name, node_uuid, device_name."""
        return self._http.request("GET", "/api/tunnels")

    def visitor_toml(self, tunnel_uuid: str) -> bytes:
        """An stcp tunnel's frpc config: `frpc -c <file>`, then 127.0.0.1:<local_port>. Holds secrets."""
        return self._http.request("GET", f"/api/tunnels/{tunnel_uuid}/visitor.toml", raw=True)
