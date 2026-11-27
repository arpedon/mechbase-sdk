package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/** One analyst finding, flat for a CMMS; `external_id`s are the caller-owned keys a sync matches on. */
@Serializable
data class Finding(
    val uuid: String,
    val status: String,
    @SerialName("fault_type") val faultType: String = "",
    @SerialName("fault_type_display") val faultTypeDisplay: String = "",
    val severity: String = "",
    @SerialName("recommended_action") val recommendedAction: String = "",
    @SerialName("due_by") val dueBy: String? = null,
    val comment: String = "",
    val evidence: JsonObject = JsonObject(emptyMap()),
    @SerialName("work_order_ref") val workOrderRef: String = "",
    @SerialName("acknowledged_at") val acknowledgedAt: String? = null,
    @SerialName("closed_at") val closedAt: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_external_id") val assetExternalId: String? = null,
    @SerialName("asset_name") val assetName: String = "",
    @SerialName("point_id") val pointId: Int? = null,
    @SerialName("point_external_id") val pointExternalId: String? = null,
    @SerialName("point_name") val pointName: String = "",
    @SerialName("point_location") val pointLocation: String = "",
    @SerialName("measurement_uuid") val measurementUuid: String? = null,
    @SerialName("measurement_external_id") val measurementExternalId: String? = null,
    @SerialName("measurement_timestamp") val measurementTimestamp: String? = null,
    @SerialName("web_url") val webUrl: String = "",
)

/** One page of findings; pass [nextCursor] back as `cursor` until it is null. */
@Serializable
data class FindingsPage(
    val items: List<Finding>,
    @SerialName("next_cursor") val nextCursor: String? = null,
)

/** A dialog choice: send [value], show [label]. */
@Serializable
data class Choice(
    val value: String = "",
    val label: String = "",
)

/** The Record finding dialog's choices; with a reading and cursor, also the evidence the server would store and the fault type a bearing-marker match suggests. */
@Serializable
data class FindingChoices(
    @SerialName("fault_types") val faultTypes: List<Choice> = emptyList(),
    val severities: List<Choice> = emptyList(),
    @SerialName("suggested_fault_type") val suggestedFaultType: String? = null,
    val evidence: JsonObject = JsonObject(emptyMap()),
)

/**
 * Where the analyst clicked the spectrum; the server derives the stored evidence from it.
 * [signal] is "" | accel | velocity | envelope; [df] is [VibrationAnalysis.sourceResolutionHz]; [shaftHz] defaults to the reading's own.
 */
@Serializable
data class FindingCursor(
    val hz: Double? = null,
    val amplitude: Double? = null,
    val unit: String = "",
    val signal: String = "",
    @SerialName("shaft_hz") val shaftHz: Double? = null,
    val df: Double? = null,
)

@Serializable
private data class FindingBody(
    @SerialName("point_id") val pointId: Int,
    @SerialName("point_sequence") val pointSequence: Int,
    @SerialName("fault_type") val faultType: String,
    val severity: String,
    @SerialName("recommended_action") val recommendedAction: String = "",
    @SerialName("due_by") val dueBy: String? = null,
    val comment: String = "",
)

private fun FindingCursor?.json(): JsonObject =
    if (this == null) JsonObject(emptyMap()) else SDK_JSON.encodeToJsonElement(FindingCursor.serializer(), this) as JsonObject

@Serializable
private data class FindingStatusBody(
    val status: String,
    @SerialName("work_order_ref") val workOrderRef: String? = null,
)

class Findings internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    /** `status` is `open`, `acknowledged` or `closed`; `since` an ISO 8601 datetime. */
    suspend fun list(
        cursor: String? = null,
        limit: Int? = null,
        since: String? = null,
        status: String? = null,
        assetId: Int? = null,
        assetExternalId: String? = null,
        pointId: Int? = null,
        pointExternalId: String? = null,
    ): FindingsPage = http.getJson(
        installationPath(installationId, "/findings/"),
        mapOf(
            "cursor" to cursor, "limit" to limit, "since" to since, "status" to status,
            "asset_id" to assetId, "asset_external_id" to assetExternalId,
            "point_id" to pointId, "point_external_id" to pointExternalId,
        ),
        FindingsPage.serializer(),
    )

    /**
     * Record a finding on a reading (also a note on the asset's thread). [faultType] and [severity] are
     * [FindingChoices] values; [dueBy] an ISO date. 404 for an unknown point, 422 for an unknown reading.
     */
    suspend fun create(
        pointId: Int,
        pointSequence: Int,
        faultType: String,
        severity: String,
        recommendedAction: String = "",
        dueBy: String? = null,
        comment: String = "",
        cursor: FindingCursor? = null,
    ): Finding {
        val body = SDK_JSON.encodeToJsonElement(
            FindingBody.serializer(),
            FindingBody(pointId, pointSequence, faultType, severity, recommendedAction, dueBy, comment),
        ) as JsonObject
        return http.postJson(installationPath(installationId, "/findings/"), JsonObject(body + cursor.json()), Finding.serializer())
    }

    /** Fault types and severities; pass the reading and [cursor] to also get the evidence and a suggested fault type. */
    suspend fun choices(pointId: Int? = null, pointSequence: Int? = null, cursor: FindingCursor? = null): FindingChoices =
        http.getJson(
            installationPath(installationId, "/findings/choices/"),
            mapOf("point_id" to pointId, "point_sequence" to pointSequence) + cursor.json().mapValues { (it.value as JsonPrimitive).content },
            FindingChoices.serializer(),
        )

    suspend fun get(uuid: String): Finding =
        http.getJson(installationPath(installationId, "/findings/$uuid/"), null, Finding.serializer())

    /** Move a finding on: `acknowledged` (a work order was raised; [workOrderRef] required) or `closed`. */
    suspend fun setStatus(uuid: String, status: String, workOrderRef: String? = null): Finding =
        http.postJson(
            installationPath(installationId, "/findings/$uuid/status/"),
            SDK_JSON.encodeToJsonElement(FindingStatusBody.serializer(), FindingStatusBody(status, workOrderRef)),
            Finding.serializer(),
        )
}

/** A bearing: [source] says whose (installation or library); only [editable] ones take update/delete. Orders are multiples of shaft speed. */
@Serializable
data class Bearing(
    val uuid: String,
    val designation: String = "",
    val manufacturer: String = "",
    val source: String = "",
    val editable: Boolean,
    @SerialName("rolling_elements") val rollingElements: Int? = null,
    val bpfo: Double,
    val bpfi: Double,
    val bsf: Double,
    val ftf: Double,
    @SerialName("ball_diameter") val ballDiameter: Double? = null,
    @SerialName("pitch_diameter") val pitchDiameter: Double? = null,
    @SerialName("contact_angle") val contactAngle: Double? = null,
    @SerialName("point_count") val pointCount: Int? = null,
    val match: String? = null,
)

/** [own]: the installation's bearings with point counts; [results]: the search or tone-match hits. */
@Serializable
data class BearingList(
    val own: List<Bearing> = emptyList(),
    val results: List<Bearing> = emptyList(),
    @SerialName("library_count") val libraryCount: Int,
)

/** A custom bearing: all four defect orders, or none and the geometry ([rollingElements], diameters, [contactAngle]) to derive them. Null fields are not sent. */
@Serializable
data class BearingInput(
    val designation: String? = null,
    val manufacturer: String? = null,
    @SerialName("rolling_elements") val rollingElements: Int? = null,
    val bpfo: Double? = null,
    val bpfi: Double? = null,
    val bsf: Double? = null,
    val ftf: Double? = null,
    @SerialName("ball_diameter") val ballDiameter: Double? = null,
    @SerialName("pitch_diameter") val pitchDiameter: Double? = null,
    @SerialName("contact_angle") val contactAngle: Double? = null,
)

/** The installation's bearings plus the shared library (read-only). */
class Bearings internal constructor(private val http: Http, private val installationId: Int) {
    private fun path(suffix: String = "") = installationPath(installationId, "/bearings$suffix")

    /**
     * [q] searches the installation's and the library's bearings (≥2 characters, ≤100 hits). Or pass
     * [order] (0 < order < 100) to match a detected tone (≤8 hits; [sideband] "1x" or "ftf").
     */
    suspend fun list(q: String? = null, order: Double? = null, sideband: String? = null): BearingList =
        http.getJson(path(), mapOf("q" to q, "order" to order, "sideband" to sideband), BearingList.serializer())

    suspend fun get(uuid: String): Bearing {
        requireUuid(uuid)
        return http.getJson(path("/$uuid"), null, Bearing.serializer())
    }

    /** [BearingInput.designation] is required. */
    suspend fun create(input: BearingInput): Bearing =
        http.postJson(path(), SDK_JSON.encodeToJsonElement(BearingInput.serializer(), input), Bearing.serializer())

    /** Only the sent fields change; new geometry without orders re-derives the orders. Library bearings 404. */
    suspend fun update(uuid: String, input: BearingInput): Bearing {
        requireUuid(uuid)
        return http.sendJson("PATCH", path("/$uuid"), SDK_JSON.encodeToJsonElement(BearingInput.serializer(), input), null, Bearing.serializer())
    }

    /** Its points lose the bearing. Library bearings 404. */
    suspend fun delete(uuid: String) {
        requireUuid(uuid)
        http.sendJson("DELETE", path("/$uuid"), null, null, Unit.serializer())
    }
}
