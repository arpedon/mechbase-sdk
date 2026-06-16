package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class PointInput(
    val name: String? = null,
    @SerialName("external_id") val externalId: String? = null,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_external_id") val assetExternalId: String? = null,
    @SerialName("transducer_type") val transducerType: String? = null,
    @SerialName("measurement_unit_code") val measurementUnitCode: String? = null,
    val location: String? = null,
    @SerialName("body_segment") val bodySegment: Int? = null,
    @SerialName("body_angle") val bodyAngle: Int? = null,
    @SerialName("machine_class") val machineClass: String? = null,
)

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

    suspend fun create(input: PointInput): MeasurementPoint =
        http.postJson(
            installationPath(installationId, "/measurement-points"),
            SDK_JSON.encodeToJsonElement(PointInput.serializer(), input),
            MeasurementPoint.serializer(),
        )

    suspend fun upsert(input: PointInput): MeasurementPoint =
        http.sendJson(
            "PUT",
            installationPath(installationId, "/measurement-points"),
            SDK_JSON.encodeToJsonElement(PointInput.serializer(), input),
            null,
            MeasurementPoint.serializer(),
        )

    suspend fun update(pointId: Int, input: PointInput): MeasurementPoint =
        http.sendJson(
            "PATCH",
            installationPath(installationId, "/measurement-points/$pointId"),
            SDK_JSON.encodeToJsonElement(PointInput.serializer(), input),
            null,
            MeasurementPoint.serializer(),
        )

    suspend fun delete(pointId: Int, cascade: Boolean = false): DeleteResult =
        http.sendJson(
            "DELETE",
            installationPath(installationId, "/measurement-points/$pointId"),
            null,
            if (cascade) mapOf("cascade" to "true") else null,
            DeleteResult.serializer(),
        )
}
