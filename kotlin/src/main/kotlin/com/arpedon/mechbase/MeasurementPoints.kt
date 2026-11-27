package com.arpedon.mechbase

import java.io.File
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.Transient
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

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
    // Analysis settings (POST and PATCH; the PUT upsert refuses them). Null leaves a field out; the clear* flags send null.
    /** Nameplate shaft speed, rpm (>= 0). */
    @SerialName("nominal_rpm") val nominalRpm: Int? = null,
    /** A library bearing's or this installation's own bearing uuid. */
    val bearing: String? = null,
    /** Bearing shaft ÷ measured shaft (>= 0.001). */
    @SerialName("speed_ratio") val speedRatio: Double? = null,
    /** Envelope band lower edge, Hz (>= 1). */
    @SerialName("envelope_band_low") val envelopeBandLow: Int? = null,
    /** Envelope band upper edge, Hz, above the lower. */
    @SerialName("envelope_band_high") val envelopeBandHigh: Int? = null,
    /** Rich-text HTML; "" (or the type default) clears the point's own instructions. */
    val instructions: String? = null,
    /** Send `nominal_rpm: null` (unset). */
    @Transient val clearNominalRpm: Boolean = false,
    /** Send `bearing: null` (remove the bearing). */
    @Transient val clearBearing: Boolean = false,
    /** Send `speed_ratio: null` (back to 1). */
    @Transient val clearSpeedRatio: Boolean = false,
    /** Send both envelope band edges as null (back to the default band); can't be combined with explicit edges. */
    @Transient val clearEnvelopeBand: Boolean = false,
)

private fun PointInput.toJson(): JsonElement {
    require(!clearEnvelopeBand || (envelopeBandLow == null && envelopeBandHigh == null)) {
        "clearEnvelopeBand with an explicit envelope band edge"
    }
    val o = SDK_JSON.encodeToJsonElement(PointInput.serializer(), this) as JsonObject
    val nulls = buildList {
        if (clearNominalRpm && nominalRpm == null) add("nominal_rpm")
        if (clearBearing && bearing == null) add("bearing")
        if (clearSpeedRatio && speedRatio == null) add("speed_ratio")
        if (clearEnvelopeBand) { add("envelope_band_low"); add("envelope_band_high") }
    }
    return JsonObject(o + nulls.associateWith { JsonNull })
}

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

    /** Run state, staleness, limits and the last 7 days for one point. */
    suspend fun context(pointId: Int): PointContext =
        http.getJson(
            installationPath(installationId, "/measurement-points/$pointId/context"),
            null,
            PointContext.serializer(),
        )

    suspend fun create(input: PointInput): MeasurementPoint =
        http.postJson(
            installationPath(installationId, "/measurement-points"),
            input.toJson(),
            MeasurementPoint.serializer(),
        )

    suspend fun upsert(input: PointInput): MeasurementPoint =
        http.sendJson(
            "PUT",
            installationPath(installationId, "/measurement-points"),
            input.toJson(),
            null,
            MeasurementPoint.serializer(),
        )

    suspend fun update(pointId: Int, input: PointInput): MeasurementPoint =
        http.sendJson(
            "PATCH",
            installationPath(installationId, "/measurement-points/$pointId"),
            input.toJson(),
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

    /** Add a photo to the point's gallery; sends `keep_reference=true`, so it never changes the reference photo (see [setReferencePhoto]; a point with none falls back to its first photo). Without that field the server makes the new photo the reference, which is what older app versions rely on. Pass a client-minted [uuid] so a retry returns the same photo. */
    suspend fun addPhoto(pointId: Int, file: File, uuid: String? = null): FileAttachment =
        http.postFile(
            installationPath(installationId, "/measurement-points/$pointId/photos/"),
            listOf(MultipartFile("file", file.name, file)),
            FileAttachment.serializer(),
            mapOf("keep_reference" to "true") + (if (uuid != null) mapOf("uuid" to uuid) else emptyMap()),
        )

    /** Delete a gallery photo by its [Photo.uuid]. A photo that's already gone throws [NotFoundException]; a non-UUID [uuid] throws [ValidationException] without a request. */
    suspend fun deletePhoto(pointId: Int, uuid: String) {
        requirePhotoUuid(uuid)
        http.sendJson("DELETE", installationPath(installationId, "/measurement-points/$pointId/photos/$uuid"), null, null, Unit.serializer())
    }

    /** Make the gallery photo [uuid] (a [Photo.uuid]) the point's reference photo; returns the updated point. A photo or point that's gone throws [NotFoundException]; a non-UUID [uuid] throws [ValidationException] without a request. */
    suspend fun setReferencePhoto(pointId: Int, uuid: String): MeasurementPoint {
        requirePhotoUuid(uuid)
        return http.sendJson(
            "PUT",
            installationPath(installationId, "/measurement-points/$pointId/reference-photo"),
            buildJsonObject { put("uuid", uuid) },
            null,
            MeasurementPoint.serializer(),
        )
    }
}
