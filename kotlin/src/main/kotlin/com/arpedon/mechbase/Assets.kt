package com.arpedon.mechbase

class Assets internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    suspend fun list(
        q: String? = null,
        zoneId: Int? = null,
        limit: Int = 50,
        offset: Int = 0,
    ): List<Asset> {
        val params = mapOf<String, Any?>(
            "q" to q,
            "zone_id" to zoneId,
            "limit" to limit,
            "offset" to offset,
        )
        return http.getJson(
            installationPath(installationId, "/assets"),
            params,
            PaginatedAssets.serializer(),
        ).items
    }

    suspend fun get(assetId: Int): Asset =
        http.getJson(
            installationPath(installationId, "/assets/$assetId"),
            null,
            Asset.serializer(),
        )
}
