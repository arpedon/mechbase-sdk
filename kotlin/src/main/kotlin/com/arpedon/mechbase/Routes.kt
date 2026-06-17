package com.arpedon.mechbase

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

    suspend fun start(routeUUID: String): Execution {
        val execution: RouteExecution = http.postJson(
            installationPath(installationId, "/routes/$routeUUID/executions"),
            null,
            RouteExecution.serializer(),
        )
        return Execution.fromExecution(http, installationId, execution)
    }

    fun execution(executionUuid: String): Execution =
        Execution(http, installationId, executionUuid, null)
}
