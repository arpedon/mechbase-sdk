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
    /** Gates staff-only UI (dashboard editing). False for service tokens and on older servers. */
    @SerialName("is_staff") val isStaff: Boolean = false,
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
    @SerialName("current_installation_id") val currentInstallationId: Int? = null, // null for a user with no installations
    /** The user's display-unit choices; null on servers that predate them. */
    @SerialName("unit_prefs") val unitPrefs: UnitPrefs? = null,
)

/** Per-quantity display units from `/api/me/` (e.g. `velocity = "mm/s"`). */
@Serializable
data class UnitPrefs(
    val acceleration: String = "",
    val velocity: String = "",
    val temperature: String = "",
    val pressure: String = "",
    val frequency: String = "",
)

/** How to show one data key of a point in the viewer's unit: `display = native * scale + offset`. */
@Serializable
data class DisplayUnit(
    val native: String,
    val unit: String,
    val scale: Double = 1.0,
    val offset: Double = 0.0,
) {
    fun convert(value: Double): Double = value * scale + offset
}

/** A point's run state, staleness, limits and last 7 days, all in native units (convert with [MeasurementPoint.displayUnits]). */
@Serializable
data class PointContext(
    @SerialName("data_key") val dataKey: String = "",
    val unit: String = "",
    /** Null when the point has no run-state reading (most non-vibration points). */
    val running: Boolean? = null,
    @SerialName("running_at") val runningAt: String? = null,
    @SerialName("stale_since") val staleSince: String? = null,
    val limits: PointLimits? = null,
    /** 6 h bin means, chronological; empty bins are omitted. */
    val week: List<TrendBin> = emptyList(),
)

@Serializable
data class PointLimits(val minor: Double? = null, val major: Double? = null)

/** One trend bin: [t] is the bin start (ISO 8601 string, like every other SDK datetime), [v] the mean. */
@Serializable
data class TrendBin(val t: String, val v: Double)

/** A gallery photo: the server `File` uuid (what `deletePhoto` takes) and its absolute URL. */
@Serializable
data class Photo(val uuid: String, val url: String)

/** `uuid` goes into the path, so anything but a canonical UUID, either case (e.g. `../10`), could reroute the DELETE. */
internal fun requirePhotoUuid(uuid: String) {
    if (runCatching { java.util.UUID.fromString(uuid).toString() == uuid.lowercase() }.getOrDefault(false)) return
    throw ValidationException("invalid photo uuid: $uuid")
}

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
    /** Absolute URLs of the asset's photo gallery, oldest first; empty on older servers. */
    @SerialName("image_urls") val imageUrls: List<String> = emptyList(),
    /** Same photos as [imageUrls], with their uuids; empty on older servers. */
    val photos: List<Photo> = emptyList(),
    /** Asset type code, if the asset has one. */
    @SerialName("asset_type") val assetType: String? = null,
)

@Serializable
data class MeasurementPoint(
    val uuid: String,
    @SerialName("point_id") val pointId: Int? = null,
    val name: String,
    @SerialName("asset_id") val assetId: Int? = null,
    // Backing columns are `blank=True, default=""` (NOT NULL by intent) but
    // they're optional metadata drift-plausible from a legacy import. We make
    // them nullable so an explicit JSON `null` (or a server regression to
    // SQL NULL) doesn't crash decode — `coerceInputValues` can't save
    // no-default properties, only nullable ones can. See issue #2.
    @SerialName("transducer_type") val transducerType: String? = null,
    @SerialName("measurement_unit_code") val measurementUnitCode: String? = null,
    val location: String? = null,
    val status: Int,
    @SerialName("external_id") val externalId: String? = null,
    // Effective working instruction (the point's override, else the
    // transducer-type default) as sanitized HTML; embedded image URLs are
    // absolute. Server always populates it; nullable keeps decode drift-safe.
    val instructions: String? = null,
    /** `[reference photo URL]`, or empty when the point has no photos (and on older servers); the full gallery is [photos]. */
    @SerialName("image_urls") val imageUrls: List<String> = emptyList(),
    /** Data keys whose display unit differs from native for this viewer; empty when none do, and on older servers. */
    @SerialName("display_units") val displayUnits: Map<String, DisplayUnit> = emptyMap(),
    /** All of the point's gallery photos with their uuids ([imageUrls] is the reference photo only); empty on older servers. */
    val photos: List<Photo> = emptyList(),
    /** Uuid of the point's reference photo (one of [photos]); null when unset, and on older servers. */
    @SerialName("reference_photo_uuid") val referencePhotoUuid: String? = null,
    /** Nameplate shaft speed, rpm. */
    @SerialName("nominal_rpm") val nominalRpm: Int? = null,
    /** The fitted bearing's uuid ([Bearings.get]). */
    val bearing: String? = null,
    /** Bearing shaft ÷ measured shaft. */
    @SerialName("speed_ratio") val speedRatio: Double = 1.0,
    @SerialName("envelope_band_low") val envelopeBandLow: Int? = null,
    @SerialName("envelope_band_high") val envelopeBandHigh: Int? = null,
    /** False: [instructions] is the transducer type's default. */
    @SerialName("has_own_instructions") val hasOwnInstructions: Boolean = false,
)

@Serializable
data class Measurement(
    val uuid: String,
    @SerialName("measurement_point_id") val measurementPointId: Int,
    // `point_sequence` is genuinely DB-nullable on the server
    // (`Measurement.point_sequence: null=True`), unlike the defaulted-text
    // fields. `coerceInputValues` can't save it (no default), so the SDK
    // must accept null. New server rows always get a value via
    // `MeasurementService.create` — null here means a legacy/imported row.
    @SerialName("point_sequence") val pointSequence: Int? = null,
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
    /** Set on single-route reads (survey, report, update); the list omits it. */
    val section: SectionRef? = null,
)

/** Lightweight section reference embedded in a route (`{section_id, name}`). */
@Serializable
data class SectionRef(
    // The server's `Section.section_id` is `PositiveIntegerField(null=True)` by
    // design (per-installation auto-increment can be unassigned). The web
    // sibling-risk audit widens `SectionRef.section_id` to `int | None`
    // (#164) so the same must happen here, pre-emptively. See issue #2.
    @SerialName("section_id") val sectionId: Int? = null,
    val name: String,
)

/** Threshold context for a measurement reading — drives "Limit X" + the
 *  OK/Watch/Alarm band. Resolved server-side from the point's threshold AlarmRules. */
@Serializable
data class MeasurementLimit(
    val minor: Double? = null,
    val major: Double? = null,
    val direction: String = "high",
    val unit: String = "",
)

/** A single check within a route. `config` is a loose JSON blob (per item-type).
 *  [instructions], [referenceImageUrl] and [limit] are first-class, resolved
 *  server-side; all additive with defaults so legacy payloads decode unchanged. */
@Serializable
data class RouteItem(
    val uuid: String,
    @SerialName("check_id") val checkId: Int? = null,
    val label: String,
    @SerialName("item_type") val itemType: String,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("zone_name") val zoneName: String? = null,
    @SerialName("measurement_point_id") val measurementPointId: Int? = null,
    val config: JsonObject = JsonObject(emptyMap()),
    val instructions: List<String> = emptyList(),
    @SerialName("reference_image_url") val referenceImageUrl: String? = null,
    val limit: MeasurementLimit? = null,
)

/** A route with its embedded section reference and ordered item list. */
@Serializable
data class RouteDetail(
    val uuid: String,
    val name: String,
    val description: String = "",
    val section: SectionRef? = null,
    val items: List<RouteItem> = emptyList(),
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
    /** Public guest page enabled; false on older servers. */
    @SerialName("guest_view") val guestView: Boolean = false,
)

/** Asset type (template), addressed by [code]. */
@Serializable
data class AssetType(
    val uuid: String,
    val code: String,
    val name: String,
    val manufacturer: String = "",
    val checklist: List<kotlinx.serialization.json.JsonElement> = emptyList(),
    @SerialName("external_id") val externalId: String? = null,
    @SerialName("asset_count") val assetCount: Int = 0,
    @SerialName("document_count") val documentCount: Int = 0,
)

/** Result of [Assets.ensureChecklist]. */
@Serializable
data class ChecklistResult(@SerialName("route_uuid") val routeUuid: String, val created: Boolean)

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

/**
 * A conditional GET's result (dashboards, point compare). Send the last [Fresh.etag] back as
 * `ifNoneMatch`: while nothing changed the server answers 304 and you get [NotModified] — keep
 * showing what you have.
 */
sealed class Conditional<out T> {
    /** A new body; [etag] is echoed verbatim (gzip makes it weak, `W/"…"`). */
    data class Fresh<out T>(val value: T, val etag: String?) : Conditional<T>()

    data object NotModified : Conditional<Nothing>()
}

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
