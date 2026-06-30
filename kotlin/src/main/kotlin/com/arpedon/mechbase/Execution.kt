package com.arpedon.mechbase

import java.io.File
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
     * to a specific asset after the walk via [triage].
     */
    suspend fun addFieldItem(
        label: String,
        itemType: String = "pass_fail",
        data: Map<String, Any?> = emptyMap(),
        zoneId: Int? = null,
        config: Map<String, Any?> = emptyMap(),
        notes: String = "",
    ): ItemResponse {
        val payload: JsonObject = buildJsonObject {
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
}
