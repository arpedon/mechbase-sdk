package com.arpedon.mechbase

import java.io.File
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

class Routes internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    suspend fun list(
        q: String? = null,
        limit: Int = 50,
        offset: Int = 0,
    ): List<Route> {
        val params = mapOf<String, Any?>("q" to q, "limit" to limit, "offset" to offset)
        return http.getJson(
            installationPath(installationId, "/routes"),
            params,
            PaginatedRoutes.serializer(),
        ).items
    }

    suspend fun get(routeUUID: String): Route =
        http.getJson(
            installationPath(installationId, "/routes/$routeUUID"),
            null,
            Route.serializer(),
        )

    /** The route plus its embedded section and ordered item list. */
    suspend fun detail(routeUUID: String): RouteDetail =
        http.getJson(
            installationPath(installationId, "/routes/$routeUUID"),
            null,
            RouteDetail.serializer(),
        )

    /**
     * Start a route execution. Online callers pass only [routeUUID] and the
     * server mints the execution uuid. Offline-first clients mint the uuid
     * locally and pass [uuid] (plus the real field [startedAt] as ISO-8601) so a
     * queued, later-pushed start lands deterministically; the server upserts on
     * uuid, so a retried push is idempotent. Both are optional → a bare call is
     * byte-for-byte the legacy empty POST.
     */
    suspend fun start(
        routeUUID: String,
        uuid: String? = null,
        startedAt: String? = null,
    ): Execution {
        val body = buildJsonObject {
            uuid?.let { put("uuid", it) }
            startedAt?.let { put("started_at", it) }
        }.takeIf { it.isNotEmpty() }
        val execution: RouteExecution = http.postJson(
            installationPath(installationId, "/routes/$routeUUID/executions"),
            body,
            RouteExecution.serializer(),
        )
        return Execution.fromExecution(http, installationId, execution)
    }

    /** Fetch one execution (e.g. the running one a 409 start named). Swift `fetchExecution`. */
    suspend fun fetchExecution(uuid: String): RouteExecution =
        http.getJson(installationPath(installationId, "/executions/$uuid"), null, RouteExecution.serializer())

    fun execution(executionUuid: String): Execution =
        Execution(http, installationId, executionUuid, null)

    private fun path(suffix: String) = installationPath(installationId, suffix)

    /** Create a route with at least one check, in reading order. A client-minted [uuid] (and item uuids) make retries safe: a retry returns the route. */
    suspend fun create(
        name: String,
        items: List<RouteItemInput>,
        description: String = "",
        uuid: String? = null,
    ): RouteDetail = http.postJson(
        path("/routes"),
        SDK_JSON.encodeToJsonElement(RouteCreateBody.serializer(), RouteCreateBody(name, description, items, uuid)),
        RouteDetail.serializer(),
    )

    /** Only non-null arguments are sent. */
    suspend fun update(routeUUID: String, name: String? = null, description: String? = null): Route {
        requireUuid(routeUUID)
        return http.sendJson(
            "PATCH", path("/routes/$routeUUID"),
            SDK_JSON.encodeToJsonElement(RoutePatchBody.serializer(), RoutePatchBody(name, description)),
            null, Route.serializer(),
        )
    }

    /** Deletes the route and its runs. 409 ([ConflictException]) while a run is in progress, and for an asset's checklist route. */
    suspend fun delete(routeUUID: String) {
        requireUuid(routeUUID)
        http.sendJson("DELETE", path("/routes/$routeUUID"), null, null, Unit.serializer())
    }

    /** The route's runs, newest first (empty cancelled runs left out). */
    suspend fun executions(routeUUID: String, limit: Int = 50, offset: Int = 0): ExecutionsPage {
        requireUuid(routeUUID)
        return http.getJson(path("/routes/$routeUUID/executions"), mapOf("limit" to limit, "offset" to offset), ExecutionsPage.serializer())
    }

    /** Replace the notes (finding/recommendation text) on any response. */
    suspend fun updateResponseNotes(responseUuid: String, notes: String): ItemResponse {
        requireUuid(responseUuid)
        return http.sendJson("PATCH", path("/responses/$responseUuid"), buildJsonObject { put("notes", notes) }, null, ItemResponse.serializer())
    }

    /** A new empty route and its first run; add checks during the walk with [Execution.addFieldItem]. A client-minted [uuid] (the run's) makes retries safe. */
    suspend fun startSurvey(name: String = "", uuid: String? = null): Survey =
        http.postJson(path("/surveys"), SDK_JSON.encodeToJsonElement(SurveyBody.serializer(), SurveyBody(name, uuid)), Survey.serializer())

    /** Append a check. 409 on an asset's checklist route. */
    suspend fun addItem(routeUUID: String, item: RouteItemInput): RouteItem {
        requireUuid(routeUUID)
        return http.postJson(path("/routes/$routeUUID/items"), SDK_JSON.encodeToJsonElement(RouteItemInput.serializer(), item), RouteItem.serializer())
    }

    /**
     * Only non-null arguments are sent. [subchecks] replaces a multi-check's steps (required when changing to
     * multi_check); a check can't change to or from measurement. Move checks with [reorderItems].
     */
    suspend fun updateItem(
        routeUUID: String,
        itemUuid: String,
        label: String? = null,
        itemType: String? = null,
        instructions: String? = null,
        unit: String? = null,
        subchecks: List<String>? = null,
    ): RouteItem {
        requireUuid(routeUUID); requireUuid(itemUuid)
        return http.sendJson(
            "PATCH", path("/routes/$routeUUID/items/$itemUuid"),
            SDK_JSON.encodeToJsonElement(RouteItemPatchBody.serializer(), RouteItemPatchBody(label, itemType, instructions, unit, subchecks)),
            null, RouteItem.serializer(),
        )
    }

    /** A check past runs answered is archived instead, so their reports keep it. */
    suspend fun deleteItem(routeUUID: String, itemUuid: String) {
        requireUuid(routeUUID); requireUuid(itemUuid)
        http.sendJson("DELETE", path("/routes/$routeUUID/items/$itemUuid"), null, null, Unit.serializer())
    }

    /** The board's drag and drop; the route is renumbered stop by stop. Returns every check's new number. */
    suspend fun reorderItems(routeUUID: String, items: List<ReorderEntry>): List<CheckNumber> {
        requireUuid(routeUUID)
        return http.postJson(
            path("/routes/$routeUUID/items/reorder"),
            buildJsonObject { put("items", JsonArray(items.map { it.toJson() })) },
            ReorderResult.serializer(),
        ).items
    }

    /** Set the check's photo (one per check: it replaces the old one). A client-minted [uuid] makes retries safe; a late retry of a replaced photo is a 409. */
    suspend fun addItemPhoto(routeUUID: String, itemUuid: String, file: File, uuid: String? = null): FileAttachment {
        requireUuid(routeUUID); requireUuid(itemUuid)
        return http.postFile(
            path("/routes/$routeUUID/items/$itemUuid/photos"),
            listOf(MultipartFile("file", file.name, file)),
            FileAttachment.serializer(),
            if (uuid != null) mapOf("uuid" to uuid) else emptyMap(),
        )
    }

    /** The check's past answers, newest first. */
    suspend fun itemHistory(routeUUID: String, itemUuid: String, limit: Int = 50, offset: Int = 0): ItemHistoryPage {
        requireUuid(routeUUID); requireUuid(itemUuid)
        return http.getJson(
            path("/routes/$routeUUID/items/$itemUuid/history"),
            mapOf("limit" to limit, "offset" to offset),
            ItemHistoryPage.serializer(),
        )
    }
}

/** Responses that were not Normal, newest run first. */
class NonConformities internal constructor(private val http: Http, private val installationId: Int) {
    /** [status] is open | resolved | all. */
    suspend fun list(status: String = "open", assetId: Int? = null, limit: Int = 50, offset: Int = 0): NonConformitiesPage =
        http.getJson(
            installationPath(installationId, "/non-conformities"),
            mapOf("status" to status, "asset_id" to assetId, "limit" to limit, "offset" to offset),
            NonConformitiesPage.serializer(),
        )

    /** A retry by whoever resolved it returns 200; resolved by someone else is a 409. */
    suspend fun resolve(responseUuid: String, comment: String = ""): NonConformity {
        requireUuid(responseUuid)
        return http.postJson(
            installationPath(installationId, "/non-conformities/$responseUuid/resolve"),
            buildJsonObject { put("comment", comment) },
            NonConformity.serializer(),
        )
    }
}
