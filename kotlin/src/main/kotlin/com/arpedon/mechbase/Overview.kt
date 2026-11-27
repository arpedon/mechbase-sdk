package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** The home screen: status counts, the top 6 needing attention ([attentionMoreCount] more → [Installation.alerts]), runs in progress, routes, recoveries. Status ints: 1 normal, 2 check, 3 warning, 4 critical. */
@Serializable
data class Overview(
    @SerialName("status_summary") val statusSummary: StatusSummary,
    val briefing: Briefing,
    @SerialName("last_reading_at") val lastReadingAt: String? = null,
    val attention: List<Alert> = emptyList(),
    @SerialName("attention_more_count") val attentionMoreCount: Int,
    @SerialName("silent_count") val silentCount: Int,
    @SerialName("running_executions") val runningExecutions: List<RunningExecution> = emptyList(),
    val routes: List<RouteSummary> = emptyList(),
    @SerialName("back_to_normal") val backToNormal: List<BackToNormal> = emptyList(),
    val sections: List<SectionStatus> = emptyList(),
)

@Serializable
data class StatusSummary(
    val total: Int,
    val nominal: Int,
    val elevated: Int,
    val warning: Int,
    val critical: Int,
    val attention: Int,
)

@Serializable
data class Briefing(
    val critical: Int,
    val warning: Int,
    val check: Int,
    val silent: Int,
    @SerialName("silent_since") val silentSince: String? = null,
    val normal: Int,
    val attention: Int,
    @SerialName("last_reading") val lastReading: String? = null,
)

/** An asset needing attention (non-Normal or silent). */
@Serializable
data class Alert(
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_name") val sectionName: String = "",
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("zone_name") val zoneName: String? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_uuid") val assetUuid: String,
    val name: String = "",
    val status: Int,
    @SerialName("is_silent") val isSilent: Boolean,
    val reason: String = "",
    @SerialName("trigger_name") val triggerName: String = "",
    @SerialName("trigger_point_id") val triggerPointId: Int? = null,
    @SerialName("trigger_route") val triggerRoute: String = "",
    @SerialName("silent_points") val silentPoints: List<String> = emptyList(),
    @SerialName("alert_since") val alertSince: String? = null,
)

@Serializable
data class RunningExecution(
    @SerialName("execution_uuid") val executionUuid: String,
    @SerialName("route_uuid") val routeUuid: String,
    @SerialName("route_name") val routeName: String = "",
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("executed_by") val executedBy: PersonRef? = null,
    val done: Int,
    val total: Int,
    @SerialName("last_completed_execution_uuid") val lastCompletedExecutionUuid: String? = null,
)

@Serializable
data class RouteSummary(
    @SerialName("route_uuid") val routeUuid: String,
    val name: String = "",
    @SerialName("item_count") val itemCount: Int,
    @SerialName("last_run") val lastRun: LastRun? = null,
)

@Serializable
data class LastRun(
    @SerialName("execution_uuid") val executionUuid: String,
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("completed_at") val completedAt: String? = null,
    @SerialName("fail_count") val failCount: Int,
)

@Serializable
data class BackToNormal(
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_name") val sectionName: String = "",
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("zone_name") val zoneName: String? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_uuid") val assetUuid: String,
    val name: String = "",
    @SerialName("recovered_at") val recoveredAt: String = "",
    val reason: String = "",
)

@Serializable
data class SectionStatus(
    @SerialName("section_id") val sectionId: Int? = null,
    val uuid: String,
    val name: String = "",
    @SerialName("asset_count") val assetCount: Int,
    @SerialName("check_count") val checkCount: Int,
    @SerialName("warning_count") val warningCount: Int,
    @SerialName("critical_count") val criticalCount: Int,
    @SerialName("worst_status") val worstStatus: Int? = null,
)

/** One feed entry. [kind]: status_change | comment | finding | route_completion. Newest first; group by local day client-side. */
@Serializable
data class Activity(
    val kind: String = "",
    val timestamp: String = "",
    val title: String = "",
    val detail: String = "",
    val state: String = "",
    val severity: Int,
    val actor: PersonRef? = null,
    @SerialName("old_status") val oldStatus: Int? = null,
    @SerialName("new_status") val newStatus: Int? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("point_id") val pointId: Int? = null,
    @SerialName("comment_id") val commentId: Int? = null,
    @SerialName("finding_uuid") val findingUuid: String? = null,
    @SerialName("execution_uuid") val executionUuid: String? = null,
    @SerialName("route_uuid") val routeUuid: String? = null,
)

/** Pass [nextCursor] back as `cursor` until it is null. */
@Serializable
data class ActivityPage(
    val items: List<Activity> = emptyList(),
    @SerialName("next_cursor") val nextCursor: String? = null,
)

/** Per-category counts ([categories]) and the typed hits. */
@Serializable
data class SearchResults(
    val query: String = "",
    val category: String? = null,
    @SerialName("total_count") val totalCount: Int,
    val categories: List<SearchCategory> = emptyList(),
    val assets: List<SearchAsset> = emptyList(),
    val sections: List<SearchSection> = emptyList(),
    val zones: List<SearchZone> = emptyList(),
    val points: List<SearchPoint> = emptyList(),
    val routes: List<SearchRoute> = emptyList(),
    @SerialName("route_items") val routeItems: List<SearchRouteItem> = emptyList(),
    val comments: List<SearchComment> = emptyList(),
    @SerialName("item_responses") val itemResponses: List<SearchNote> = emptyList(),
)

/** A search category; pass [slug] as `category` to fill only that list. */
@Serializable
data class SearchCategory(
    val key: String = "",
    val slug: String = "",
    val label: String = "",
    val count: Int,
    val selected: Boolean,
)

@Serializable
data class SearchAsset(
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_name") val sectionName: String = "",
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("zone_name") val zoneName: String? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    val uuid: String,
    val name: String = "",
    val status: Int,
)

@Serializable
data class SearchSection(
    @SerialName("section_id") val sectionId: Int? = null,
    val uuid: String,
    val name: String = "",
)

@Serializable
data class SearchZone(
    @SerialName("zone_id") val zoneId: Int? = null,
    val uuid: String,
    val name: String = "",
    val alias: String = "",
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_name") val sectionName: String = "",
)

@Serializable
data class SearchPoint(
    @SerialName("point_id") val pointId: Int? = null,
    val uuid: String,
    val name: String = "",
    val location: String = "",
    @SerialName("transducer_type") val transducerType: String = "",
    @SerialName("transducer_type_label") val transducerTypeLabel: String = "",
    val status: Int,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_name") val assetName: String = "",
    @SerialName("section_name") val sectionName: String = "",
)

@Serializable
data class SearchRoute(
    val uuid: String,
    val name: String = "",
    val description: String = "",
)

@Serializable
data class SearchRouteItem(
    val uuid: String,
    @SerialName("check_id") val checkId: Int? = null,
    val label: String = "",
    @SerialName("route_uuid") val routeUuid: String,
    @SerialName("route_name") val routeName: String = "",
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_name") val assetName: String? = null,
)

@Serializable
data class SearchComment(
    @SerialName("comment_id") val commentId: Int,
    @SerialName("body_text") val bodyText: String = "",
    @SerialName("author_name") val authorName: String = "",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_name") val assetName: String = "",
)

/** A route response whose notes matched. */
@Serializable
data class SearchNote(
    @SerialName("response_uuid") val responseUuid: String,
    val notes: String = "",
    @SerialName("execution_uuid") val executionUuid: String,
    @SerialName("route_uuid") val routeUuid: String,
    @SerialName("route_name") val routeName: String = "",
    @SerialName("started_at") val startedAt: String? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_name") val assetName: String? = null,
)

/** Running hours over the window the server used ([windowStart]..[windowEnd]). */
@Serializable
data class RunningHours(
    @SerialName("production_from") val productionFrom: String? = null,
    @SerialName("production_to") val productionTo: String? = null,
    @SerialName("window_start") val windowStart: String = "",
    @SerialName("window_end") val windowEnd: String = "",
    @SerialName("stale_hours") val staleHours: Int,
    val rows: List<RunningHoursRow> = emptyList(),
)

/** One Production point. [state]: on | off | stale, null when it never reported. */
@Serializable
data class RunningHoursRow(
    val state: String? = null,
    @SerialName("last_ping") val lastPing: String? = null,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_name") val sectionName: String = "",
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("zone_name") val zoneName: String? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_uuid") val assetUuid: String,
    @SerialName("asset_name") val assetName: String = "",
    @SerialName("point_id") val pointId: Int? = null,
    @SerialName("range_hours") val rangeHours: Double,
    @SerialName("lifetime_hours") val lifetimeHours: Double,
    val segments: List<HoursSegment> = emptyList(),
)

@Serializable
data class HoursSegment(
    @SerialName("start_pct") val startPct: Double,
    @SerialName("width_pct") val widthPct: Double,
)

/** [state]: on | off | stale. */
@Serializable
data class ProductionState(
    val state: String? = null,
    @SerialName("last_ping") val lastPing: String? = null,
)

/** Email/push notification settings; [notificationsMuted] is account-wide. */
@Serializable
data class NotificationSettings(
    @SerialName("severity_threshold") val severityThreshold: Int,
    @SerialName("status_changes") val statusChanges: Boolean,
    @SerialName("route_completions") val routeCompletions: Boolean,
    val exports: Boolean,
    @SerialName("notifications_muted") val notificationsMuted: Boolean,
    @SerialName("threshold_choices") val thresholdChoices: List<ThresholdChoice> = emptyList(),
)

@Serializable
data class ThresholdChoice(
    val value: Int,
    val label: String = "",
)

/** [result]: sent | logged. */
@Serializable
data class EmailTestResult(
    val result: String = "",
)

/** Who did something: a user id and display name. */
@Serializable
data class PersonRef(
    val id: Int,
    val name: String = "",
)

@Serializable
internal data class NotificationSettingsUpdate(
    @SerialName("severity_threshold") val severityThreshold: Int? = null,
    @SerialName("status_changes") val statusChanges: Boolean? = null,
    @SerialName("route_completions") val routeCompletions: Boolean? = null,
    val exports: Boolean? = null,
    @SerialName("notifications_muted") val notificationsMuted: Boolean? = null,
)
