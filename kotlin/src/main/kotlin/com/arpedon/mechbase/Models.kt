package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

@Serializable
data class User(
    val id: Int,
    val username: String,
    @SerialName("full_name") val fullName: String,
    val email: String = "",
)

@Serializable
data class InstallationDto(
    @SerialName("installation_id") val installationId: Int,
    val name: String,
)

@Serializable
data class Me(
    val user: User,
    val installations: List<InstallationDto>,
    @SerialName("current_installation_id") val currentInstallationId: Int,
)

@Serializable
data class Asset(
    val uuid: String,
    @SerialName("asset_id") val assetId: Int? = null,
    val name: String,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("machine_class") val machineClass: String = "",
    @SerialName("equipment_type") val equipmentType: String = "",
    val status: Int,
    @SerialName("external_id") val externalId: String? = null,
)

@Serializable
data class MeasurementPoint(
    val uuid: String,
    @SerialName("point_id") val pointId: Int? = null,
    val name: String,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("transducer_type") val transducerType: String,
    @SerialName("measurement_unit_code") val measurementUnitCode: String,
    val location: String,
    val status: Int,
    @SerialName("external_id") val externalId: String? = null,
)

@Serializable
data class Measurement(
    val uuid: String,
    @SerialName("measurement_point_id") val measurementPointId: Int,
    @SerialName("point_sequence") val pointSequence: Int,
    val data: JsonObject = JsonObject(emptyMap()),
    val status: String,
    val notes: String = "",
    @SerialName("created_at") val createdAt: String,
    @SerialName("file_url") val fileUrl: String? = null,
    @SerialName("external_id") val externalId: String? = null,
)

@Serializable
data class Route(
    val uuid: String,
    val name: String,
    val description: String = "",
)

@Serializable
data class RouteExecution(
    val uuid: String,
    @SerialName("route_uuid") val routeUuid: String,
    val status: String,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("completed_at") val completedAt: String? = null,
    @SerialName("session_id") val sessionId: String,
)

@Serializable
data class ItemResponse(
    val uuid: String,
    @SerialName("route_item_uuid") val routeItemUuid: String,
    val data: JsonObject = JsonObject(emptyMap()),
    val notes: String = "",
    val status: Int,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
internal data class PaginatedAssets(
    val items: List<Asset>,
    val total: Int = 0,
    val limit: Int = 0,
    val offset: Int = 0,
)

@Serializable
internal data class PaginatedMeasurementPoints(
    val items: List<MeasurementPoint>,
    val total: Int = 0,
    val limit: Int = 0,
    val offset: Int = 0,
)

@Serializable
internal data class PaginatedMeasurements(
    val items: List<Measurement>,
    val total: Int = 0,
    val limit: Int = 0,
    val offset: Int = 0,
)

@Serializable
internal data class PaginatedRoutes(
    val items: List<Route>,
    val total: Int = 0,
    val limit: Int = 0,
    val offset: Int = 0,
)

@Serializable
data class Section(
    val uuid: String,
    @SerialName("section_id") val sectionId: Int? = null,
    val name: String,
    @SerialName("external_id") val externalId: String? = null,
)

@Serializable
data class Zone(
    val uuid: String,
    @SerialName("zone_id") val zoneId: Int? = null,
    val name: String,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("external_id") val externalId: String? = null,
)

@Serializable
data class DeleteResult(val deleted: Boolean, val uuid: String)

@Serializable
data class BatchItemResult(
    val index: Int,
    val status: String,
    @SerialName("measurement_point_id") val measurementPointId: Int? = null,
    @SerialName("point_sequence") val pointSequence: Int? = null,
    val uuid: String? = null,
    @SerialName("external_id") val externalId: String? = null,
    val detail: String? = null,
)

@Serializable
data class BatchResult(
    val created: Int,
    val duplicates: Int,
    val errors: Int,
    val results: List<BatchItemResult>,
)

@Serializable
data class FileAttachment(
    val uuid: String,
    val name: String,
    val kind: String,
    @SerialName("file_url") val fileUrl: String,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
internal data class PaginatedSections(
    val items: List<Section>, val total: Int = 0, val limit: Int = 0, val offset: Int = 0,
)

@Serializable
internal data class PaginatedZones(
    val items: List<Zone>, val total: Int = 0, val limit: Int = 0, val offset: Int = 0,
)

@Serializable
internal data class CursorMeasurements(
    val items: List<Measurement>,
    @SerialName("next_cursor") val nextCursor: String? = null,
)

/** Convert a loose `Map<String, Any?>` into a `JsonObject` for request bodies. */
fun Map<String, Any?>.toJsonObject(): JsonObject =
    JsonObject(mapValues { (_, v) -> anyToJson(v) })

private fun anyToJson(v: Any?): JsonElement = when (v) {
    null -> JsonNull
    is JsonElement -> v
    is Boolean -> JsonPrimitive(v)
    is Int -> JsonPrimitive(v)
    is Long -> JsonPrimitive(v)
    is Float -> JsonPrimitive(v)
    is Double -> JsonPrimitive(v)
    is Number -> JsonPrimitive(v)
    is String -> JsonPrimitive(v)
    is Map<*, *> -> JsonObject(
        v.entries.associate { (k, vv) -> k.toString() to anyToJson(vv) }
    )
    is Iterable<*> -> kotlinx.serialization.json.JsonArray(v.map { anyToJson(it) })
    is Array<*> -> kotlinx.serialization.json.JsonArray(v.map { anyToJson(it) })
    else -> JsonPrimitive(v.toString())
}

/** Convert a `JsonObject` back to a plain `Map<String, Any?>` for ergonomic access. */
fun JsonObject.toAnyMap(): Map<String, Any?> =
    entries.associate { (k, v) -> k to jsonToAny(v) }

private fun jsonToAny(e: JsonElement): Any? = when (e) {
    is JsonNull -> null
    is JsonPrimitive -> e.booleanOrNull ?: e.intOrNull ?: e.doubleOrNull ?: e.jsonPrimitive.content
    is JsonObject -> e.toAnyMap()
    is kotlinx.serialization.json.JsonArray -> e.jsonArray.map { jsonToAny(it) }
    else -> e.jsonObject.toAnyMap()
}
