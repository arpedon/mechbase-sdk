package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** One mapped channel of a MaintNode group. [state] is ok | stale | waiting. */
@Serializable
data class DeviceChannel(
    val uuid: String,
    val channel: Int? = null,
    @SerialName("point_id") val pointId: Int,
    @SerialName("point_name") val pointName: String = "",
    @SerialName("asset_id") val assetId: Int,
    @SerialName("asset_name") val assetName: String = "",
    val sensor: String = "",
    @SerialName("last_seen_at") val lastSeenAt: String? = null,
    @SerialName("stale_since") val staleSince: String? = null,
    val state: String = "",
)

@Serializable
data class DeviceGroup(
    val uuid: String,
    val name: String = "",
    @SerialName("hardware_type") val hardwareType: String = "",
    @SerialName("hardware_config") val hardwareConfig: JsonObject = JsonObject(emptyMap()),
    val interval: Int = 0,
    @SerialName("sample_rate") val sampleRate: Int? = null,
    val samples: Int? = null,
    val channels: List<DeviceChannel> = emptyList(),
)

/** Remote access to a service on a device's site: http opens in a browser at [webUrl]; stcp needs frpc and the visitor file (staff). */
@Serializable
data class Tunnel(
    val uuid: String,
    val name: String = "",
    val label: String = "",
    val kind: String = "",
    @SerialName("staff_only") val staffOnly: Boolean = false,
    @SerialName("web_url") val webUrl: String? = null,
    @SerialName("local_port") val localPort: Int? = null,
    @SerialName("visitor_url") val visitorUrl: String? = null,
    // Set only in the staff list across installations (MechbaseClient.tunnels).
    @SerialName("installation_id") val installationId: Int? = null,
    @SerialName("installation_name") val installationName: String? = null,
    @SerialName("node_uuid") val nodeUuid: String? = null,
    @SerialName("device_name") val deviceName: String? = null,
)

/** A MaintNode with its groups, channels and the tunnels you may open. [healthUrl] is set for staff only. */
@Serializable
data class Device(
    @SerialName("node_uuid") val nodeUuid: String,
    val name: String = "",
    @SerialName("is_online") val isOnline: Boolean = false,
    @SerialName("last_seen_at") val lastSeenAt: String? = null,
    @SerialName("claimed_at") val claimedAt: String? = null,
    val health: JsonObject = JsonObject(emptyMap()),
    @SerialName("health_warnings") val healthWarnings: List<String> = emptyList(),
    @SerialName("health_url") val healthUrl: String? = null,
    val groups: List<DeviceGroup> = emptyList(),
    val tunnels: List<Tunnel> = emptyList(),
)

@Serializable
data class SourceGroup(
    val uuid: String,
    val name: String = "",
    @SerialName("hardware_type") val hardwareType: String = "",
)

/** One data source feeding a point. [sourceType] is mqtt | maintnode. */
@Serializable
data class Source(
    val uuid: String,
    @SerialName("source_type") val sourceType: String = "",
    @SerialName("device_id") val deviceId: String = "",
    @SerialName("device_name") val deviceName: String? = null,
    val group: SourceGroup? = null,
    val channel: Int? = null,
    val sensor: String = "",
    @SerialName("sensor_config") val sensorConfig: JsonObject? = null,
    @SerialName("is_active") val isActive: Boolean = true,
    @SerialName("last_seen_at") val lastSeenAt: String? = null,
    @SerialName("stale_since") val staleSince: String? = null,
)

/** The installation's MaintNode devices. */
class Devices internal constructor(private val http: Http, private val installationId: Int) {
    private fun path(suffix: String = "") = installationPath(installationId, "/devices$suffix")

    /** Devices needing attention first. */
    suspend fun list(): List<Device> = http.getJson(path(), null, ListSerializer(Device.serializer()))

    suspend fun get(nodeUuid: String): Device {
        requireUuid(nodeUuid)
        return http.getJson(path("/$nodeUuid"), null, Device.serializer())
    }

    suspend fun rename(nodeUuid: String, name: String): Device {
        requireUuid(nodeUuid)
        return http.sendJson("PATCH", path("/$nodeUuid"), buildJsonObject { put("name", name) }, null, Device.serializer())
    }

    /**
     * Change a group: the group edit page's fields (name, interval, sample_rate, samples, hardware_id,
     * hardware_address, Modbus connection fields). Fields left out keep their value. Returns the device.
     */
    suspend fun updateGroup(nodeUuid: String, groupUuid: String, fields: JsonObject): Device {
        requireUuid(nodeUuid); requireUuid(groupUuid)
        return http.sendJson("PATCH", path("/$nodeUuid/groups/$groupUuid"), fields, null, Device.serializer())
    }
}

/**
 * A point's data sources. Fields are the add-source page's (source_type, mqtt_device_id, device, group,
 * group_name, hardware_type, mn_channel, register_address, sensor, sensitivity, …).
 */
class Sources internal constructor(private val http: Http, private val installationId: Int) {
    private fun path(pointId: Int, suffix: String = "") =
        installationPath(installationId, "/measurement-points/$pointId/sources$suffix")

    suspend fun list(pointId: Int): List<Source> = http.getJson(path(pointId), null, ListSerializer(Source.serializer()))

    /** Omitted fields take the page's defaults; a MaintNode source with no group creates one. */
    suspend fun create(pointId: Int, fields: JsonObject): Source = http.postJson(path(pointId), fields, Source.serializer())

    /** Fields left out keep their value; a source keeps its type, device and group. */
    suspend fun update(pointId: Int, sourceUuid: String, fields: JsonObject): Source {
        requireUuid(sourceUuid)
        return http.sendJson("PATCH", path(pointId, "/$sourceUuid"), fields, null, Source.serializer())
    }

    suspend fun delete(pointId: Int, sourceUuid: String) {
        requireUuid(sourceUuid)
        http.sendJson("DELETE", path(pointId, "/$sourceUuid"), null, null, Unit.serializer())
    }
}
