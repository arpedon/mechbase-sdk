package com.arpedon.mechbase

import java.io.File
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

@Serializable
data class MeasurementInput(
    @SerialName("measurement_point_id") val measurementPointId: Int? = null,
    @SerialName("measurement_point_external_id") val measurementPointExternalId: String? = null,
    val data: JsonObject,
    val notes: String? = null,
    @SerialName("session_id") val sessionId: String? = null,
    val timestamp: String? = null,
    @SerialName("external_id") val externalId: String? = null,
) {
    constructor(
        measurementPointId: Int? = null,
        measurementPointExternalId: String? = null,
        data: Map<String, Any?>,
        notes: String? = null,
        sessionId: String? = null,
        timestamp: String? = null,
        externalId: String? = null,
    ) : this(
        measurementPointId, measurementPointExternalId, data.toJsonObject(),
        notes, sessionId, timestamp, externalId,
    )
}

@Serializable
private data class BatchBody(val items: List<MeasurementInput>)

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

    suspend fun createBatch(items: List<MeasurementInput>): BatchResult =
        http.postJson(
            installationPath(installationId, "/measurements/batch/"),
            SDK_JSON.encodeToJsonElement(BatchBody.serializer(), BatchBody(items)),
            BatchResult.serializer(),
        )

    suspend fun addFile(measurementUuid: String, file: File): FileAttachment =
        http.postFile(
            installationPath(installationId, "/measurements/$measurementUuid/files/"),
            listOf(MultipartFile("file", file.name, file)),
            FileAttachment.serializer(),
        )

    suspend fun listForPoint(
        pointId: Int,
        limit: Int = 50,
        offset: Int = 0,
        createdFrom: String? = null,
        createdTo: String? = null,
    ): List<Measurement> {
        val params = mapOf<String, Any?>(
            "limit" to limit,
            "offset" to offset,
            "created_from" to createdFrom,
            "created_to" to createdTo,
        )
        return http.getJson(
            installationPath(installationId, "/measurement-points/$pointId/measurements/"),
            params,
            PaginatedMeasurements.serializer(),
        ).items
    }

    fun iterForPoint(
        pointId: Int,
        createdFrom: String? = null,
        createdTo: String? = null,
        pageSize: Int = 100,
    ): Flow<Measurement> = flow {
        var cursor = ""
        val path = installationPath(installationId, "/measurement-points/$pointId/measurements/")
        while (true) {
            val params = mutableMapOf<String, Any?>("limit" to pageSize, "cursor" to cursor)
            if (createdFrom != null) params["created_from"] = createdFrom
            if (createdTo != null) params["created_to"] = createdTo
            val page = http.getJson(path, params, CursorMeasurements.serializer(), stripEmpty = false)
            page.items.forEach { emit(it) }
            val next = page.nextCursor
            if (next.isNullOrEmpty()) break
            cursor = next
        }
    }
}
