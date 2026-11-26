package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Optional export filters; unset ones are omitted. Datetimes are ISO 8601. */
@Serializable
data class ExportFilters(
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("asset_external_id") val assetExternalId: String? = null,
    @SerialName("point_id") val pointId: Int? = null,
    @SerialName("point_external_id") val pointExternalId: String? = null,
    @SerialName("transducer_type") val transducerType: String? = null,
    val status: String? = null,
    val action: String? = null,
    @SerialName("route_id") val routeId: String? = null,
    @SerialName("created_from") val createdFrom: String? = null,
    @SerialName("created_to") val createdTo: String? = null,
    @SerialName("updated_since") val updatedSince: String? = null,
)

@Serializable
private data class ExportCreateBody(val dataset: String, val format: String, val filters: ExportFilters)

/** A queued export (202). Poll [Exports.status] until `state` is done. */
@Serializable
data class ExportJob(
    @SerialName("job_uuid") val jobUuid: String,
    val state: String,
    @SerialName("status_url") val statusUrl: String,
)

@Serializable
data class ExportStatus(
    @SerialName("job_uuid") val jobUuid: String,
    val dataset: String,
    @SerialName("file_format") val fileFormat: String,
    val state: String,
    @SerialName("row_count") val rowCount: Int? = null,
    @SerialName("byte_size") val byteSize: Long? = null,
    @SerialName("download_url") val downloadUrl: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
    val error: String = "",
    @SerialName("created_at") val createdAt: String,
)

/** Bulk analytics exports (asynchronous: create, poll, download). */
class Exports internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    suspend fun create(dataset: String, format: String = "csv", filters: ExportFilters = ExportFilters()): ExportJob =
        http.postJson(
            installationPath(installationId, "/analytics/exports/"),
            SDK_JSON.encodeToJsonElement(ExportCreateBody.serializer(), ExportCreateBody(dataset, format, filters)),
            ExportJob.serializer(),
        )

    suspend fun status(jobUuid: String): ExportStatus =
        http.getJson(installationPath(installationId, "/analytics/exports/$jobUuid/"), null, ExportStatus.serializer())

    /** The finished file's raw bytes. Reads the signed link from [status], so the job must be done. */
    suspend fun download(jobUuid: String): ByteArray {
        val st = status(jobUuid)
        val link = st.downloadUrl ?: throw MechbaseException("Export $jobUuid has no file yet (${st.state})", status = 410)
        // Keep only the signature; the path resolves against the client's base URL.
        val sig = java.net.URI(link).rawQuery.orEmpty().split("&")
            .firstOrNull { it.startsWith("sig=") }?.removePrefix("sig=")
            ?.let { java.net.URLDecoder.decode(it, "UTF-8") }
        return http.getBytes(installationPath(installationId, "/analytics/exports/$jobUuid/download/"), mapOf("sig" to sig))
    }
}
