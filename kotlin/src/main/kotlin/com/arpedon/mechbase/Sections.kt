package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class SectionInput(
    val name: String? = null,
    @SerialName("external_id") val externalId: String? = null,
)

class Sections internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    suspend fun list(
        q: String? = null,
        limit: Int = 50,
        offset: Int = 0,
    ): List<Section> {
        val params = mapOf<String, Any?>(
            "q" to q,
            "limit" to limit,
            "offset" to offset,
        )
        return http.getJson(
            installationPath(installationId, "/sections"),
            params,
            PaginatedSections.serializer(),
        ).items
    }

    suspend fun get(sectionId: Int): Section =
        http.getJson(
            installationPath(installationId, "/sections/$sectionId"),
            null,
            Section.serializer(),
        )

    suspend fun create(input: SectionInput): Section =
        http.postJson(
            installationPath(installationId, "/sections"),
            SDK_JSON.encodeToJsonElement(SectionInput.serializer(), input),
            Section.serializer(),
        )

    suspend fun upsert(input: SectionInput): Section =
        http.sendJson(
            "PUT",
            installationPath(installationId, "/sections"),
            SDK_JSON.encodeToJsonElement(SectionInput.serializer(), input),
            null,
            Section.serializer(),
        )

    suspend fun update(sectionId: Int, input: SectionInput): Section =
        http.sendJson(
            "PATCH",
            installationPath(installationId, "/sections/$sectionId"),
            SDK_JSON.encodeToJsonElement(SectionInput.serializer(), input),
            null,
            Section.serializer(),
        )

    suspend fun delete(sectionId: Int, cascade: Boolean = false): DeleteResult =
        http.sendJson(
            "DELETE",
            installationPath(installationId, "/sections/$sectionId"),
            null,
            if (cascade) mapOf("cascade" to "true") else null,
            DeleteResult.serializer(),
        )
}
