package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** A board in the picker; [uuid] is null for the automatic board. */
@Serializable
data class DashboardSummary(
    val uuid: String? = null,
    val name: String = "",
    @SerialName("is_default") val isDefault: Boolean,
    @SerialName("is_automatic") val isAutomatic: Boolean,
)

/** A board: sections of live tiles. Poll every [refreshSeconds] with the last ETag ([Dashboards.default]). */
@Serializable
data class Dashboard(
    val uuid: String? = null,
    val name: String = "",
    @SerialName("is_default") val isDefault: Boolean,
    @SerialName("is_automatic") val isAutomatic: Boolean,
    @SerialName("refresh_seconds") val refreshSeconds: Int,
    val readiness: Boolean,
    val sections: List<BoardSection> = emptyList(),
)

@Serializable
data class BoardSection(
    val uuid: String? = null,
    val title: String = "",
    val meta: String = "",
    val latest: String? = null,
    val status: Int,
    @SerialName("status_label") val statusLabel: String = "",
    val health: Int,
    val readiness: String = "",
    val tiles: List<Tile> = emptyList(),
)

/** One point on a board: latest value, status, limits and today's trend. [uuid] is null on the automatic board; [state] on | off | stale for Production points. */
@Serializable
data class Tile(
    val uuid: String? = null,
    val label: String = "",
    @SerialName("custom_label") val customLabel: String = "",
    @SerialName("point_id") val pointId: Int? = null,
    @SerialName("point_uuid") val pointUuid: String,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_name") val assetName: String = "",
    @SerialName("transducer_type") val transducerType: String = "",
    val value: Double? = null,
    val unit: String? = null,
    val decimals: Int,
    @SerialName("measured_at") val measuredAt: String? = null,
    val lags: Boolean,
    val status: Int,
    @SerialName("status_label") val statusLabel: String = "",
    val alarm: Boolean,
    @SerialName("stale_since") val staleSince: String? = null,
    val state: String? = null,
    @SerialName("state_since") val stateSince: String? = null,
    val limits: PointLimits? = null,
    val trend: DayTrend? = null,
    val timeline: List<StateInterval>? = null,
)

/** Today's trend (local day, `X-Timezone`) with its value range. */
@Serializable
data class DayTrend(
    val start: String = "",
    val end: String = "",
    val low: Double,
    val high: Double,
    val points: List<TrendBin> = emptyList(),
)

/** An on/off interval; an open one has [end] null (draw to now). */
@Serializable
data class StateInterval(
    val start: String = "",
    val end: String? = null,
    @SerialName("is_on") val isOn: Boolean,
    val status: Int,
    @SerialName("is_open") val isOpen: Boolean,
)

/** A saved board section, as section CRUD returns it. */
@Serializable
data class DashboardSection(
    val uuid: String,
    val title: String = "",
    val position: Int,
)

/** A saved tile, as tile CRUD returns it; [section] is its section uuid. */
@Serializable
data class TileRef(
    val uuid: String,
    val section: String = "",
    @SerialName("point_id") val pointId: Int? = null,
    val label: String = "",
    @SerialName("custom_label") val customLabel: String = "",
    val position: Int,
)

/** One section of a [Dashboards.reorder] layout: its uuid and its tiles' uuids in order. */
@Serializable
data class LayoutSection(
    @SerialName("id") val sectionUuid: String,
    @SerialName("tiles") val tileUuids: List<String> = emptyList(),
)

@Serializable
private data class LayoutBody(val sections: List<LayoutSection>)

@Serializable
private data class DashboardPatch(
    val name: String? = null,
    @SerialName("is_default") val isDefault: Boolean? = null,
)

@Serializable
private data class TilesBody(val section: String, @SerialName("point_ids") val pointIds: List<Int>)

/** Dashboards: read for every member; create/edit/reorder are staff-only (403 otherwise, gate on [User.isStaff]). */
class Dashboards internal constructor(private val http: Http, private val installationId: Int) {
    private fun path(suffix: String = "") = installationPath(installationId, "/dashboards$suffix")

    /** Saved boards by position; with none, the automatic board alone. */
    suspend fun list(): List<DashboardSummary> = http.getJson(path(), null, ListSerializer(DashboardSummary.serializer()))

    /** The default board, else the first, else the automatic one. Pass the last [Conditional.Fresh.etag] as [ifNoneMatch] when polling. */
    suspend fun default(ifNoneMatch: String? = null): Conditional<Dashboard> =
        http.getConditional(path("/default"), null, Dashboard.serializer(), ifNoneMatch)

    suspend fun get(dashboardUuid: String, ifNoneMatch: String? = null): Conditional<Dashboard> {
        requireUuid(dashboardUuid)
        return http.getConditional(path("/$dashboardUuid"), null, Dashboard.serializer(), ifNoneMatch)
    }

    /** Blank [name] → "New dashboard"; the installation's first board becomes its default. */
    suspend fun create(name: String = ""): DashboardSummary =
        http.postJson(path(), buildJsonObject { put("name", name) }, DashboardSummary.serializer())

    /** Only non-null arguments are sent; [isDefault] true clears the flag on every other board. */
    suspend fun update(dashboardUuid: String, name: String? = null, isDefault: Boolean? = null): DashboardSummary {
        requireUuid(dashboardUuid)
        return http.sendJson(
            "PATCH", path("/$dashboardUuid"),
            SDK_JSON.encodeToJsonElement(DashboardPatch.serializer(), DashboardPatch(name, isDefault)),
            null, DashboardSummary.serializer(),
        )
    }

    /** Deleting the default hands the flag to the next board. */
    suspend fun delete(dashboardUuid: String) {
        requireUuid(dashboardUuid)
        http.sendJson("DELETE", path("/$dashboardUuid"), null, null, Unit.serializer())
    }

    /** Persist the automatic board as "All monitored points". 422 when nothing is monitored. */
    suspend fun saveAutomatic(): DashboardSummary = http.postJson(path("/save-automatic"), null, DashboardSummary.serializer())

    /** Sections in order, each with its tiles in order (a tile may change section). Left-out ones keep their place; a bad id is a 422 and nothing changes. */
    suspend fun reorder(dashboardUuid: String, sections: List<LayoutSection>) {
        requireUuid(dashboardUuid)
        http.postJson(
            path("/$dashboardUuid/reorder"),
            SDK_JSON.encodeToJsonElement(LayoutBody.serializer(), LayoutBody(sections)),
            Unit.serializer(),
        )
    }

    /** Appended last; blank [title] → "New section". */
    suspend fun addSection(dashboardUuid: String, title: String = ""): DashboardSection {
        requireUuid(dashboardUuid)
        return http.postJson(path("/$dashboardUuid/sections"), buildJsonObject { put("title", title) }, DashboardSection.serializer())
    }

    /** A blank [title] is a 422. */
    suspend fun renameSection(dashboardUuid: String, sectionUuid: String, title: String): DashboardSection {
        requireUuid(dashboardUuid); requireUuid(sectionUuid)
        return http.sendJson(
            "PATCH", path("/$dashboardUuid/sections/$sectionUuid"),
            buildJsonObject { put("title", title) }, null, DashboardSection.serializer(),
        )
    }

    /** Deletes its tiles too. */
    suspend fun deleteSection(dashboardUuid: String, sectionUuid: String) {
        requireUuid(dashboardUuid); requireUuid(sectionUuid)
        http.sendJson("DELETE", path("/$dashboardUuid/sections/$sectionUuid"), null, null, Unit.serializer())
    }

    /** Append points to a section in order; points already in it are skipped, so only the new tiles come back. */
    suspend fun addTiles(dashboardUuid: String, sectionUuid: String, pointIds: List<Int>): List<TileRef> {
        requireUuid(dashboardUuid)
        return http.postJson(
            path("/$dashboardUuid/tiles"),
            SDK_JSON.encodeToJsonElement(TilesBody.serializer(), TilesBody(sectionUuid, pointIds)),
            ListSerializer(TileRef.serializer()),
        )
    }

    /** A blank [label] falls back to the point's own. */
    suspend fun renameTile(dashboardUuid: String, tileUuid: String, label: String): TileRef {
        requireUuid(dashboardUuid); requireUuid(tileUuid)
        return http.sendJson(
            "PATCH", path("/$dashboardUuid/tiles/$tileUuid"),
            buildJsonObject { put("label", label) }, null, TileRef.serializer(),
        )
    }

    suspend fun removeTile(dashboardUuid: String, tileUuid: String) {
        requireUuid(dashboardUuid); requireUuid(tileUuid)
        http.sendJson("DELETE", path("/$dashboardUuid/tiles/$tileUuid"), null, null, Unit.serializer())
    }
}
