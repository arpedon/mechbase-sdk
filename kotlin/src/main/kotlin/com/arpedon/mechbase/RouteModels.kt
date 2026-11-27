package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.Transient
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject

/** A run in a route's history; [maxStatus] is the worst answer (1 normal … 4 critical), null without answers. */
@Serializable
data class ExecutionSummary(
    val uuid: String,
    @SerialName("route_uuid") val routeUuid: String,
    val status: String = "",
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("completed_at") val completedAt: String? = null,
    @SerialName("session_id") val sessionId: String = "",
    val number: Int,
    @SerialName("executed_by") val executedBy: PersonRef? = null,
    @SerialName("answered_count") val answeredCount: Int,
    @SerialName("passed_count") val passedCount: Int,
    @SerialName("non_conformity_count") val nonConformityCount: Int,
    @SerialName("max_status") val maxStatus: Int? = null,
)

@Serializable
data class ExecutionsPage(
    val items: List<ExecutionSummary> = emptyList(),
    val total: Int = 0,
    val limit: Int = 0,
    val offset: Int = 0,
)

/** The run report: answered checks by stop, [missing] unanswered checks, non-conformities worst first. [canAmend]: staff or the runner, on a completed run. */
@Serializable
data class ExecutionReport(
    val execution: ExecutionSummary,
    val route: Route,
    @SerialName("can_amend") val canAmend: Boolean,
    val totals: ReportTotals,
    val groups: List<ReportGroup> = emptyList(),
    val missing: List<ReportCheck> = emptyList(),
    val exceptions: List<ReportNonConformity> = emptyList(),
)

@Serializable
data class ReportTotals(
    val checks: Int,
    val answered: Int,
    val passed: Int,
    @SerialName("non_conformities") val nonConformities: Int,
)

/** One stop of the report: its checks' answers in order. */
@Serializable
data class ReportGroup(
    @SerialName("zone_id") val zoneId: Int? = null,
    val label: String = "",
    val entries: List<ReportEntry> = emptyList(),
)

@Serializable
data class ReportEntry(
    val check: ReportCheck,
    val response: ReportResponse,
)

@Serializable
data class ReportCheck(
    val uuid: String,
    @SerialName("check_id") val checkId: Int,
    val label: String = "",
    @SerialName("item_type") val itemType: String = "",
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_name") val assetName: String? = null,
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("measurement_point_id") val measurementPointId: Int? = null,
    val config: JsonObject = JsonObject(emptyMap()),
)

/** An answer with its photos and, for a measurement check, its linked reading. Photo URLs are signed and expire. */
@Serializable
data class ReportResponse(
    val uuid: String,
    val data: JsonObject = JsonObject(emptyMap()),
    val notes: String = "",
    val status: Int,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("resolved_by") val resolvedBy: PersonRef? = null,
    @SerialName("resolution_comment") val resolutionComment: String = "",
    val photos: List<ReportPhoto> = emptyList(),
    val reading: ReportReading? = null,
)

/** A report photo; [kind] is "photo", or "thermogram" for a thermography reading's image. */
@Serializable
data class ReportPhoto(
    val uuid: String,
    val kind: String = "",
    val url: String = "",
    val name: String = "",
)

/** The reading a measurement check's answer links to. */
@Serializable
data class ReportReading(
    val uuid: String,
    @SerialName("point_id") val pointId: Int? = null,
    @SerialName("point_sequence") val pointSequence: Int? = null,
    val status: Int,
    val data: JsonObject = JsonObject(emptyMap()),
    val notes: String = "",
    @SerialName("created_at") val createdAt: String = "",
)

/** A non-Normal answer in the report. */
@Serializable
data class ReportNonConformity(
    @SerialName("response_uuid") val responseUuid: String,
    @SerialName("route_item_uuid") val routeItemUuid: String,
    val name: String = "",
    val status: Int,
    val resolved: Boolean,
)

/** A response that was not Normal, with its resolution. */
@Serializable
data class NonConformity(
    @SerialName("response_uuid") val responseUuid: String,
    @SerialName("execution_uuid") val executionUuid: String,
    @SerialName("route_uuid") val routeUuid: String,
    @SerialName("route_name") val routeName: String = "",
    @SerialName("route_item_uuid") val routeItemUuid: String,
    val label: String = "",
    @SerialName("asset_id") val assetId: Int? = null,
    val status: Int,
    val notes: String = "",
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("resolved_by") val resolvedBy: PersonRef? = null,
    @SerialName("resolution_comment") val resolutionComment: String = "",
)

@Serializable
data class NonConformitiesPage(
    val items: List<NonConformity> = emptyList(),
    val total: Int = 0,
    val limit: Int = 0,
    val offset: Int = 0,
)

/** A blank survey: the new empty route and its first run. */
@Serializable
data class Survey(
    val route: Route,
    val execution: RouteExecution,
)

/** A check's new number after a reorder. */
@Serializable
data class CheckNumber(
    val uuid: String,
    @SerialName("check_id") val checkId: Int,
)

/** One past answer to a check. */
@Serializable
data class ItemHistoryEntry(
    @SerialName("response_uuid") val responseUuid: String,
    @SerialName("execution_uuid") val executionUuid: String,
    @SerialName("execution_status") val executionStatus: String = "",
    @SerialName("executed_by") val executedBy: PersonRef? = null,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("created_at") val createdAt: String = "",
    val status: Int,
    val data: JsonObject = JsonObject(emptyMap()),
    val notes: String = "",
    @SerialName("measurement_uuid") val measurementUuid: String? = null,
    @SerialName("point_sequence") val pointSequence: Int? = null,
)

@Serializable
data class ItemHistoryPage(
    val items: List<ItemHistoryEntry> = emptyList(),
    val total: Int = 0,
    val limit: Int = 0,
    val offset: Int = 0,
)

/**
 * A new check. [itemType] is pass_fail | numerical | multi_check | measurement; a measurement check needs
 * [measurementPointId] (its asset is the point's when [assetId] is null), a multi_check at least one of
 * [subchecks]. A client-minted [uuid] makes retries safe.
 */
@Serializable
data class RouteItemInput(
    val label: String,
    @SerialName("item_type") val itemType: String = "pass_fail",
    val instructions: String = "",
    val unit: String = "",
    val subchecks: List<String> = emptyList(),
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("measurement_point_id") val measurementPointId: Int? = null,
    val uuid: String? = null,
)

/**
 * One check's place in [Routes.reorderItems]: [position] orders it within its stop. [zoneId] / [assetId]
 * move it; null keeps it where it is, [clearZone] / [clearAsset] take it off its zone / asset.
 */
@Serializable
data class ReorderEntry(
    val uuid: String,
    val position: Int,
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @Transient val clearZone: Boolean = false,
    @Transient val clearAsset: Boolean = false,
)

internal fun ReorderEntry.toJson(): JsonElement {
    val o = SDK_JSON.encodeToJsonElement(ReorderEntry.serializer(), this) as JsonObject
    val nulls = buildList {
        if (clearZone && zoneId == null) add("zone_id")
        if (clearAsset && assetId == null) add("asset_id")
    }
    return JsonObject(o + nulls.associateWith { JsonNull })
}

@Serializable
internal data class RouteCreateBody(
    val name: String,
    val description: String = "",
    val items: List<RouteItemInput>,
    val uuid: String? = null,
)

@Serializable
internal data class RoutePatchBody(val name: String? = null, val description: String? = null)

@Serializable
internal data class RouteItemPatchBody(
    val label: String? = null,
    @SerialName("item_type") val itemType: String? = null,
    val instructions: String? = null,
    val unit: String? = null,
    val subchecks: List<String>? = null,
)

@Serializable
internal data class ReorderResult(val items: List<CheckNumber> = emptyList())

@Serializable
internal data class SurveyBody(val name: String = "", val uuid: String? = null)
