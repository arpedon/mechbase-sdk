package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ZoneInput(
    val name: String? = null,
    @SerialName("external_id") val externalId: String? = null,
    @SerialName("section_id") val sectionId: Int? = null,
    @SerialName("section_external_id") val sectionExternalId: String? = null,
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
}
