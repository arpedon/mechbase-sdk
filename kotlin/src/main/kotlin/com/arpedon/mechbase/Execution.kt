package com.arpedon.mechbase

import java.io.File
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** Operations on a single in-flight route execution. */
class Execution internal constructor(
    private val http: Http,
    private val installationId: Int,
    val uuid: String,
    val execution: RouteExecution? = null,
) {
    internal companion object {
        internal fun fromExecution(http: Http, iid: Int, ex: RouteExecution): Execution =
            Execution(http, iid, ex.uuid, ex)
    }

    private fun url(suffix: String): String =
        installationPath(installationId, "/executions/$uuid$suffix")

    suspend fun respond(
        routeItemUUID: String,
        data: Map<String, Any?>,
        notes: String = "",
        photos: List<File> = emptyList(),
        idempotencyKey: String? = null,
    ): ItemResponse {
        val payload: JsonObject = buildJsonObject {
            put("route_item_uuid", JsonPrimitive(routeItemUUID))
            put("data", data.toJsonObject())
            put("notes", JsonPrimitive(notes))
        }
        val headers = idempotencyKey?.let { mapOf("X-Idempotency-Key" to it) } ?: emptyMap()
        return if (photos.isEmpty()) {
            http.postJson(url("/responses"), payload, ItemResponse.serializer(), headers)
        } else {
            val parts = photos.map { f -> MultipartFile("files", f.name, f) }
            http.postMultipart(url("/responses/upload"), payload, parts, ItemResponse.serializer(), headers)
        }
    }

    /**
     * Append a field-discovered item to the execution.
     *
     * Items are zone-anchored ([zoneId]) or route-level (`null`). Bind the item
     * to a specific asset after the walk via [triage]. A client-minted [uuid] (the new item's) makes it
     * retry-safe: a retry returns the response already recorded; a uuid another item has throws [ConflictException].
     * Send it lowercase (the server echoes it lowercase). Older servers ignore it (no retry safety there).
     */
    suspend fun addFieldItem(
        label: String,
        itemType: String = "pass_fail",
        data: Map<String, Any?> = emptyMap(),
        zoneId: Int? = null,
        config: Map<String, Any?> = emptyMap(),
        notes: String = "",
        uuid: String? = null,
    ): ItemResponse {
        val payload: JsonObject = buildJsonObject {
            if (uuid != null) put("uuid", JsonPrimitive(uuid))
            put("label", JsonPrimitive(label))
            put("item_type", JsonPrimitive(itemType))
            put("data", data.toJsonObject())
            put("zone_id", if (zoneId == null) JsonNull else JsonPrimitive(zoneId))
            put("config", config.toJsonObject())
            put("notes", JsonPrimitive(notes))
        }
        return http.postJson(url("/items"), payload, ItemResponse.serializer())
    }

    suspend fun triage(routeItemUUID: String, assetId: Int): ItemResponse {
        val payload = buildJsonObject {
            put("route_item_uuid", JsonPrimitive(routeItemUUID))
            put("asset_id", JsonPrimitive(assetId))
        }
        return http.postJson(url("/triage"), payload, ItemResponse.serializer())
    }

    suspend fun complete(): RouteExecution =
        http.postJson(url("/complete"), null, RouteExecution.serializer())

    /**
     * Cancel an empty in-progress run (an abandoned start). Idempotent: a retry on a
     * cancelled run returns 200 again. Throws [ConflictException] when the run is
     * completed or holds a real answer — only empty starts are cancellable.
     */
    suspend fun cancel(): RouteExecution =
        http.postJson(url("/cancel"), null, RouteExecution.serializer())

    /** What the web run report shows; works for a run in progress too. */
    suspend fun report(): ExecutionReport = http.getJson(url("/report"), null, ExecutionReport.serializer())

    private fun amend(itemUuid: String, suffix: String = ""): String {
        requireUuid(itemUuid)
        return url("/amend/$itemUuid$suffix")
    }

    private fun idempotency(key: String?) = key?.let { mapOf("X-Idempotency-Key" to it) } ?: emptyMap()

    // Amending a completed run: staff or the runner ([ExecutionReport.canAmend]).

    /** Answer a check the completed run left unanswered. Send [idempotencyKey] so a retry returns the answer it made. */
    suspend fun amendAnswer(
        itemUuid: String,
        data: Map<String, Any?>,
        notes: String = "",
        idempotencyKey: String? = null,
    ): ItemResponse = http.postJson(
        amend(itemUuid, "/answer"),
        buildJsonObject { put("data", data.toJsonObject()); put("notes", notes) },
        ItemResponse.serializer(),
        idempotency(idempotencyKey),
    )

    /** Replace a check's notes; the old text stays in the run's amendment log. */
    suspend fun amendNotes(itemUuid: String, notes: String): ItemResponse =
        http.sendJson("PATCH", amend(itemUuid, "/notes"), buildJsonObject { put("notes", notes) }, null, ItemResponse.serializer())

    /** Add a photo to the check's answer (or its reading). A client-minted [uuid] makes retries safe. */
    suspend fun amendAddPhoto(itemUuid: String, file: File, uuid: String? = null): FileAttachment =
        http.postFile(
            amend(itemUuid, "/photos"),
            listOf(MultipartFile("file", file.name, file)),
            FileAttachment.serializer(),
            if (uuid != null) mapOf("uuid" to uuid) else emptyMap(),
        )

    /** Take a photo off the check (it is kept on the run). Repeating is a no-op. */
    suspend fun amendRemovePhoto(itemUuid: String, fileUuid: String) {
        requireUuid(fileUuid)
        http.sendJson("DELETE", amend(itemUuid, "/photos/$fileUuid"), null, null, Unit.serializer())
    }

    /**
     * Record a reading for a measurement check, as the web measurement form: [value] (the point type's
     * main scalar), [comment], [images], [dataFile] (thermography: required; vibration: a value or a
     * waveform file). Send [idempotencyKey]: a retry returns the answer it made, a key another reading used is a 409.
     */
    suspend fun amendReading(
        itemUuid: String,
        value: Double? = null,
        comment: String = "",
        images: List<File> = emptyList(),
        dataFile: File? = null,
        idempotencyKey: String? = null,
    ): ItemResponse = http.postFile(
        amend(itemUuid, "/reading"),
        images.map { MultipartFile("images", it.name, it) } + listOfNotNull(dataFile?.let { MultipartFile("data_file", it.name, it) }),
        ItemResponse.serializer(),
        buildMap { value?.let { put("value", it.toString()) }; put("comment", comment) },
        idempotency(idempotencyKey),
    )
}
