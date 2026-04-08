package com.arpedon.mechbase

class MeasurementPoints internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    suspend fun list(
        q: String? = null,
        assetId: Int? = null,
        transducerType: String? = null,
        limit: Int = 50,
        offset: Int = 0,
    ): List<MeasurementPoint> {
        val params = mapOf<String, Any?>(
            "q" to q,
            "asset_id" to assetId,
            "transducer_type" to transducerType,
            "limit" to limit,
            "offset" to offset,
        )
        return http.getJson(
            installationPath(installationId, "/measurement-points"),
            params,
            PaginatedMeasurementPoints.serializer(),
        ).items
    }

    suspend fun get(pointId: Int): MeasurementPoint =
        http.getJson(
            installationPath(installationId, "/measurement-points/$pointId"),
            null,
            MeasurementPoint.serializer(),
        )
}
