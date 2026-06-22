package com.arpedon.mechbase

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

    fun execution(executionUuid: String): Execution =
        Execution(http, installationId, executionUuid, null)
}
