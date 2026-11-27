package com.arpedon.mechbase

import java.io.File
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonElement

/** Upsert/update body for asset types. Nulls are omitted. */
@Serializable
data class AssetTypeInput(
    val code: String? = null,
    val name: String? = null,
    val manufacturer: String? = null,
    val checklist: List<JsonElement>? = null,
    @SerialName("external_id") val externalId: String? = null,
)

/** Asset types (templates), addressed by `code`: name, manufacturer, checklist and documents. */
class AssetTypes internal constructor(private val http: Http, private val installationId: Int) {
    private fun path(code: String, suffix: String = ""): String {
        if (code.isBlank() || code.any { it in "/?#%" }) throw ValidationException("invalid asset type code: $code")
        return installationPath(installationId, "/asset-types/$code$suffix")
    }

    private fun body(input: AssetTypeInput) = SDK_JSON.encodeToJsonElement(AssetTypeInput.serializer(), input)

    suspend fun list(): List<AssetType> =
        http.getJson(installationPath(installationId, "/asset-types"), null, ListSerializer(AssetType.serializer()))

    suspend fun get(code: String): AssetType = http.getJson(path(code), null, AssetType.serializer())

    /** Create or update the type keyed on `input.code`. */
    suspend fun upsert(input: AssetTypeInput): AssetType =
        http.sendJson("PUT", installationPath(installationId, "/asset-types"), body(input), null, AssetType.serializer())

    suspend fun update(code: String, input: AssetTypeInput): AssetType =
        http.sendJson("PATCH", path(code), body(input), null, AssetType.serializer())

    suspend fun delete(code: String): DeleteResult =
        http.sendJson("DELETE", path(code), null, null, DeleteResult.serializer())

    suspend fun documents(code: String): List<Document> =
        http.getJson(path(code, "/documents"), null, ListSerializer(Document.serializer()))

    /** Upload a document; same defaults as [Documents.add]. */
    suspend fun addDocument(
        code: String,
        file: File,
        filename: String = "",
        kind: String = "attachment",
        uuid: String? = null,
    ): Document =
        http.postFile(
            path(code, "/documents"),
            listOf(MultipartFile("file", filename.ifEmpty { file.name }, file)),
            Document.serializer(),
            buildMap { put("kind", kind.ifEmpty { "attachment" }); uuid?.let { put("uuid", it) } },
        )

    suspend fun deleteDocument(code: String, uuid: String) {
        requireUuid(uuid)
        http.sendJson("DELETE", path(code, "/documents/$uuid"), null, null, Unit.serializer())
    }
}
