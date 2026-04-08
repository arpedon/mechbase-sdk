package com.arpedon.mechbase

import java.io.File
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

class Measurements internal constructor(
    private val http: Http,
    private val installationId: Int,
) {
    suspend fun create(
        pointId: Int,
        data: Map<String, Any?>,
        notes: String = "",
        sessionId: String? = null,
        timestamp: String? = null,
        file: File? = null,
    ): Measurement {
        val payload: JsonObject = buildJsonObject {
            put("measurement_point_id", JsonPrimitive(pointId))
            put("data", data.toJsonObject())
            put("notes", JsonPrimitive(notes))
            if (sessionId != null) put("session_id", JsonPrimitive(sessionId))
            if (timestamp != null) put("timestamp", JsonPrimitive(timestamp))
        }

        return if (file == null) {
            http.postJson(
                installationPath(installationId, "/measurements/"),
                payload,
                Measurement.serializer(),
            )
        } else {
            http.postMultipart(
                installationPath(installationId, "/measurements/upload/"),
                payload,
                listOf(MultipartFile("file", file.name, file)),
                Measurement.serializer(),
            )
        }
    }

    suspend fun listForPoint(
        pointId: Int,
        limit: Int = 50,
        offset: Int = 0,
    ): List<Measurement> {
        val params = mapOf<String, Any?>("limit" to limit, "offset" to offset)
        return http.getJson(
            installationPath(installationId, "/measurement-points/$pointId/measurements/"),
            params,
            PaginatedMeasurements.serializer(),
        ).items
    }
}
