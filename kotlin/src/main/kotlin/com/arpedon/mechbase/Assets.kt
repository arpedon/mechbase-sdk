package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class AssetInput(
    val name: String? = null,
    @SerialName("external_id") val externalId: String? = null,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_external_id") val sectionExternalId: String? = null,
    @SerialName("zone_id") val zoneId: Int? = null,
    @SerialName("zone_external_id") val zoneExternalId: String? = null,
    @SerialName("equipment_type") val equipmentType: String? = null,
    @SerialName("machine_class") val machineClass: String? = null,
)

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

    suspend fun create(input: AssetInput): Asset =
        http.postJson(
            installationPath(installationId, "/assets"),
            SDK_JSON.encodeToJsonElement(AssetInput.serializer(), input),
            Asset.serializer(),
        )

    suspend fun upsert(input: AssetInput): Asset =
        http.sendJson(
            "PUT",
            installationPath(installationId, "/assets"),
            SDK_JSON.encodeToJsonElement(AssetInput.serializer(), input),
            null,
            Asset.serializer(),
        )

    suspend fun update(assetId: Int, input: AssetInput): Asset =
        http.sendJson(
            "PATCH",
            installationPath(installationId, "/assets/$assetId"),
            SDK_JSON.encodeToJsonElement(AssetInput.serializer(), input),
            null,
            Asset.serializer(),
        )

    suspend fun delete(assetId: Int, cascade: Boolean = false): DeleteResult =
        http.sendJson(
            "DELETE",
            installationPath(installationId, "/assets/$assetId"),
            null,
            if (cascade) mapOf("cascade" to "true") else null,
            DeleteResult.serializer(),
        )
}
