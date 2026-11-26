package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

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
