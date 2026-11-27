package com.arpedon.mechbase

import java.io.File
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.serializer

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
    /** Type code. null omits the field (leaves it untouched); see [clearAssetType] to send explicit null. */
    @SerialName("asset_type") val assetType: String? = null,
    /** Send `"asset_type": null` (clears the type) when [assetType] is null. */
    @kotlinx.serialization.Transient val clearAssetType: Boolean = false,
)

private fun AssetInput.toJson(): kotlinx.serialization.json.JsonElement {
    val o = SDK_JSON.encodeToJsonElement(AssetInput.serializer(), this) as kotlinx.serialization.json.JsonObject
    return if (clearAssetType && assetType == null) kotlinx.serialization.json.JsonObject(o + ("asset_type" to kotlinx.serialization.json.JsonNull)) else o
}

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
            input.toJson(),
            Asset.serializer(),
        )

    suspend fun upsert(input: AssetInput): Asset =
        http.sendJson(
            "PUT",
            installationPath(installationId, "/assets"),
            input.toJson(),
            null,
            Asset.serializer(),
        )

    suspend fun update(assetId: Int, input: AssetInput): Asset =
        http.sendJson(
            "PATCH",
            installationPath(installationId, "/assets/$assetId"),
            input.toJson(),
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

    /** Create (or find) the asset's checklist route from its type. 422 if the asset has no type or the type's checklist is empty. */
    suspend fun ensureChecklist(assetId: Int): ChecklistResult =
        http.postJson(installationPath(installationId, "/assets/$assetId/checklist"), null, ChecklistResult.serializer())

    /** Re-read the type's checklist into the asset's checks route (`created` false). 422 once a run was completed, while one is open, or without a checks route or checklist. */
    suspend fun rebuildChecklist(assetId: Int): ChecklistResult =
        http.postJson(installationPath(installationId, "/assets/$assetId/checklist/rebuild"), null, ChecklistResult.serializer())

    /** Flip the asset's Production point on/off (as the web's toggle). 422 when it has no Production point. */
    suspend fun flipProduction(assetId: Int): ProductionState =
        http.postJson(installationPath(installationId, "/assets/$assetId/production/flip"), null, ProductionState.serializer())

    /** Append a photo to the asset's gallery. Pass a client-minted [uuid] so a retry returns the same photo. */
    suspend fun addPhoto(assetId: Int, file: File, uuid: String? = null): FileAttachment =
        http.postFile(
            installationPath(installationId, "/assets/$assetId/photos/"),
            listOf(MultipartFile("file", file.name, file)),
            FileAttachment.serializer(),
            if (uuid != null) mapOf("uuid" to uuid) else emptyMap(),
        )

    /** Delete a gallery photo by its [Photo.uuid]. A photo that's already gone throws [NotFoundException]; a non-UUID [uuid] throws [ValidationException] without a request. */
    suspend fun deletePhoto(assetId: Int, uuid: String) {
        requirePhotoUuid(uuid)
        http.sendJson("DELETE", installationPath(installationId, "/assets/$assetId/photos/$uuid"), null, null, Unit.serializer())
    }
}
