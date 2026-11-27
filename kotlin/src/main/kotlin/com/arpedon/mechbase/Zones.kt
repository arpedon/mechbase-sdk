package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import java.io.File
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer

@Serializable
data class ZoneInput(
    val name: String? = null,
    @SerialName("external_id") val externalId: String? = null,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_external_id") val sectionExternalId: String? = null,
    @SerialName("guest_view") val guestView: Boolean? = null,
)

/** A zone document; [inherited] ones belong to the zone's type (not deletable here). [url] is signed and expires. */
@Serializable
data class ZoneDocument(
    val uuid: String,
    val name: String = "",
    val kind: String = "",
    val url: String = "",
    @SerialName("created_at") val createdAt: String = "",
    val inherited: Boolean,
)

/** A zone photo; [takenAt] from the file name or EXIF, null when unknown. [url] is signed and expires. */
@Serializable
data class ZonePhoto(
    val uuid: String,
    val name: String = "",
    val url: String = "",
    @SerialName("taken_at") val takenAt: String? = null,
    @SerialName("created_at") val createdAt: String = "",
)

class Zones internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    suspend fun list(
        q: String? = null,
        sectionId: Int? = null,
        limit: Int = 50,
        offset: Int = 0,
    ): List<Zone> {
        val params = mapOf<String, Any?>(
            "q" to q,
            "section_id" to sectionId,
            "limit" to limit,
            "offset" to offset,
        )
        return http.getJson(
            installationPath(installationId, "/zones"),
            params,
            PaginatedZones.serializer(),
        ).items
    }

    suspend fun get(zoneId: Int): Zone =
        http.getJson(
            installationPath(installationId, "/zones/$zoneId"),
            null,
            Zone.serializer(),
        )

    suspend fun create(input: ZoneInput): Zone =
        http.postJson(
            installationPath(installationId, "/zones"),
            SDK_JSON.encodeToJsonElement(ZoneInput.serializer(), input),
            Zone.serializer(),
        )

    suspend fun upsert(input: ZoneInput): Zone =
        http.sendJson(
            "PUT",
            installationPath(installationId, "/zones"),
            SDK_JSON.encodeToJsonElement(ZoneInput.serializer(), input),
            null,
            Zone.serializer(),
        )

    suspend fun update(zoneId: Int, input: ZoneInput): Zone =
        http.sendJson(
            "PATCH",
            installationPath(installationId, "/zones/$zoneId"),
            SDK_JSON.encodeToJsonElement(ZoneInput.serializer(), input),
            null,
            Zone.serializer(),
        )

    suspend fun delete(zoneId: Int, cascade: Boolean = false): DeleteResult =
        http.sendJson(
            "DELETE",
            installationPath(installationId, "/zones/$zoneId"),
            null,
            if (cascade) mapOf("cascade" to "true") else null,
            DeleteResult.serializer(),
        )

    /** The zone's own documents by kind and name, then its type's ([ZoneDocument.inherited]). */
    suspend fun documents(zoneId: Int): List<ZoneDocument> =
        http.getJson(installationPath(installationId, "/zones/$zoneId/documents"), null, ListSerializer(ZoneDocument.serializer()))

    /** [kind]: attachment | drawing | datasheet | manual | check_sheet | test_report. A client-minted [uuid] makes retries safe. */
    suspend fun addDocument(zoneId: Int, file: File, kind: String = "attachment", uuid: String? = null, filename: String = ""): ZoneDocument =
        http.postFile(
            installationPath(installationId, "/zones/$zoneId/documents"),
            listOf(MultipartFile("file", filename.ifEmpty { file.name }, file)),
            ZoneDocument.serializer(),
            buildMap { put("kind", kind.ifEmpty { "attachment" }); uuid?.let { put("uuid", it) } },
        )

    /** The zone's own documents only; 404 when already gone. */
    suspend fun deleteDocument(zoneId: Int, uuid: String) {
        requireUuid(uuid)
        http.sendJson("DELETE", installationPath(installationId, "/zones/$zoneId/documents/$uuid"), null, null, Unit.serializer())
    }

    /** By capture time, oldest first; unknown capture times last. */
    suspend fun photos(zoneId: Int): List<ZonePhoto> =
        http.getJson(installationPath(installationId, "/zones/$zoneId/photos"), null, ListSerializer(ZonePhoto.serializer()))

    /** A client-minted [uuid] makes retries safe; the same file (name and size) again returns the photo already there. */
    suspend fun addPhoto(zoneId: Int, file: File, uuid: String? = null): ZonePhoto =
        http.postFile(
            installationPath(installationId, "/zones/$zoneId/photos"),
            listOf(MultipartFile("file", file.name, file)),
            ZonePhoto.serializer(),
            if (uuid != null) mapOf("uuid" to uuid) else emptyMap(),
        )

    /** 404 when already gone. */
    suspend fun deletePhoto(zoneId: Int, uuid: String) {
        requireUuid(uuid)
        http.sendJson("DELETE", installationPath(installationId, "/zones/$zoneId/photos/$uuid"), null, null, Unit.serializer())
    }
}
