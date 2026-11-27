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
    /** The credentials push to Balena; null on older servers. */
    @SerialName("token_push") val tokenPush: TokenPush? = null,
    /** Applied vs current config; null on older servers. */
    val config: DeviceConfig? = null,
    /** Hardware the device last reported (HAT addresses, USB-201, Modbus reachability); null until it does. */
    val hardware: JsonObject? = null,
)

/** [state]: none | queued | pushed | failed. After a claim, wait for `pushed`, then the first heartbeat. */
@Serializable
data class TokenPush(
    val state: String = "",
    @SerialName("queued_at") val queuedAt: String? = null,
    @SerialName("pushed_at") val pushedAt: String? = null,
    @SerialName("failed_at") val failedAt: String? = null,
)

/** [isCurrent] is null until the device reports a config version (or has its own token). */
@Serializable
data class DeviceConfig(
    @SerialName("applied_version") val appliedVersion: String? = null,
    @SerialName("current_version") val currentVersion: String = "",
    @SerialName("is_current") val isCurrent: Boolean? = null,
)

/**
 * What the provision page shows: [state] claim | member | taken | not_found | unreachable (`member`
 * only when the device is in this installation; retry `unreachable`).
 */
@Serializable
data class DeviceLookup(
    val state: String = "",
    @SerialName("node_uuid") val nodeUuid: String,
    val name: String? = null,
    @SerialName("installation_id") val installationId: Int? = null,
    @SerialName("installation_name") val installationName: String? = null,
    @SerialName("is_online") val isOnline: Boolean? = null,
)

/** A group's channel slots; [slots] is null for Modbus (only used registers are listed). */
@Serializable
data class GroupChannels(
    val uuid: String,
    val name: String = "",
    @SerialName("hardware_type") val hardwareType: String = "",
    val slots: Int? = null,
    val channels: List<ChannelSlot> = emptyList(),
)

/** One channel slot, free ([used] false) or feeding a point. [state]: ok | stale | waiting. */
@Serializable
data class ChannelSlot(
    val channel: Int,
    val used: Boolean,
    @SerialName("mapping_uuid") val mappingUuid: String? = null,
    @SerialName("is_active") val isActive: Boolean? = null,
    @SerialName("point_id") val pointId: Int? = null,
    @SerialName("point_name") val pointName: String? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_name") val assetName: String? = null,
    val sensor: String? = null,
    val state: String? = null,
)

@Serializable
private data class ClaimBody(@SerialName("balena_uuid") val balenaUuid: String, val name: String? = null)

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

    /** Claim state of a device by its Balena uuid (the label QR's `/provision/<balena_uuid>/`). Service tokens 403. */
    suspend fun lookup(balenaUuid: String): DeviceLookup {
        requireHex(balenaUuid)
        return http.getJson(path("/lookup/$balenaUuid"), null, DeviceLookup.serializer())
    }

    /**
     * Claim a device into this installation and queue its credentials push (201); a device already here
     * resends them and keeps its name (200). 409 when another installation has it. Then poll [get]:
     * [TokenPush.state] `pushed` → first heartbeat ([Device.isOnline]) → [DeviceConfig.isCurrent].
     */
    suspend fun claim(balenaUuid: String, name: String? = null): Device =
        http.postJson(path(), SDK_JSON.encodeToJsonElement(ClaimBody.serializer(), ClaimBody(balenaUuid, name)), Device.serializer())

    /** Queue the push of the device's current token again; follow [Device.tokenPush]. */
    suspend fun resendCredentials(nodeUuid: String): Device {
        requireUuid(nodeUuid)
        return http.postJson(path("/$nodeUuid/credentials"), null, Device.serializer())
    }

    /** Per group, every channel slot (16 for hat/ul; USB-201 physically uses 0–7) with the point it feeds, or free. */
    suspend fun channels(nodeUuid: String): List<GroupChannels> {
        requireUuid(nodeUuid)
        return http.getJson(path("/$nodeUuid/channels"), null, ListSerializer(GroupChannels.serializer()))
    }

    /**
     * Add a group, as the add-source page: group_name, hardware_type (hat | ul | modbus), hardware_address /
     * hardware_id (USB DAQ), interval (s), sample_rate, samples, and the Modbus connection fields. Returns the device.
     */
    suspend fun createGroup(nodeUuid: String, fields: JsonObject): Device {
        requireUuid(nodeUuid)
        return http.postJson(path("/$nodeUuid/groups"), fields, Device.serializer())
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

// A Balena uuid is 32 hex digits (dashed or not); anything else could reroute the path.
private fun requireHex(id: String) {
    if (id.isNotEmpty() && id.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' || it == '-' }) return
    throw ValidationException("invalid balena uuid: $id")
}
