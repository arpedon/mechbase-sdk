package com.arpedon.mechbase

import java.io.File
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer

/** A comment's pointer at a measurement point, optionally one reading. */
@Serializable
data class CommentReference(
    @SerialName("point_id") val pointId: Int? = null,
    @SerialName("point_sequence") val pointSequence: Int? = null,
)

/** One entry in an asset's thread. [body] is rich-text HTML; [editable] is false for other authors' and findings' notes. */
@Serializable
data class Comment(
    val id: Int,
    val body: String = "",
    @SerialName("body_text") val bodyText: String = "",
    @SerialName("author_name") val authorName: String = "",
    @SerialName("created_at") val createdAt: String,
    @SerialName("edited_at") val editedAt: String? = null,
    val references: List<CommentReference> = emptyList(),
    @SerialName("is_finding") val isFinding: Boolean = false,
    val editable: Boolean = false,
)

@Serializable
data class CommentsPage(
    val items: List<Comment> = emptyList(),
    val total: Int = 0,
    val limit: Int = 0,
    val offset: Int = 0,
)

/** What to attach to a comment: point [pointId] of the asset, optionally one reading by [pointSequence]. */
@Serializable
data class CommentReferenceIn(
    @SerialName("point_id") val pointId: Int,
    @SerialName("point_sequence") val pointSequence: Int? = null,
)

// No defaults on purpose: SDK_JSON drops defaulted fields, and an empty reference list must be sent.
@Serializable
private data class CommentBody(val body: String, val references: List<CommentReferenceIn>)

@Serializable
data class Document(
    val uuid: String,
    val name: String = "",
    val kind: String = "",
    val url: String = "",
    @SerialName("created_at") val createdAt: String = "",
)

/** `scope` is "point" or "installation" (read-only defaults). */
@Serializable
data class AlarmRule(
    val uuid: String,
    val scope: String = "",
    val method: String = "",
    @SerialName("data_key") val dataKey: String = "",
    @SerialName("effective_data_key") val effectiveDataKey: String = "",
    val direction: String = "",
    @SerialName("minor_threshold") val minorThreshold: Double? = null,
    @SerialName("major_threshold") val majorThreshold: Double? = null,
    @SerialName("threshold_mode") val thresholdMode: String = "",
    val source: String? = null,
)

@Serializable
private data class AlarmRuleCreate(
    val method: String,
    @SerialName("data_key") val dataKey: String,
    val direction: String,
    @SerialName("minor_threshold") val minorThreshold: Double,
    @SerialName("major_threshold") val majorThreshold: Double,
)

// Nulls are omitted (explicitNulls = false), so only the given fields are sent.
@Serializable
private data class AlarmRulePatch(
    @SerialName("data_key") val dataKey: String? = null,
    val direction: String? = null,
    @SerialName("minor_threshold") val minorThreshold: Double? = null,
    @SerialName("major_threshold") val majorThreshold: Double? = null,
)

private fun requireUuid(uuid: String) {
    if (runCatching { java.util.UUID.fromString(uuid).toString() == uuid.lowercase() }.getOrDefault(false)) return
    throw ValidationException("invalid uuid: $uuid")
}

/** An asset's comment thread. 403 ([AuthException]) means not the author, or a finding's note. */
class Comments internal constructor(private val http: Http, private val installationId: Int) {
    private fun path(assetId: Int, suffix: String = "") =
        installationPath(installationId, "/assets/$assetId/comments$suffix")

    suspend fun list(assetId: Int, limit: Int? = null, offset: Int? = null): CommentsPage =
        http.getJson(path(assetId), mapOf("limit" to limit, "offset" to offset), CommentsPage.serializer())

    suspend fun create(assetId: Int, body: String, references: List<CommentReferenceIn> = emptyList()): Comment =
        http.postJson(
            path(assetId),
            SDK_JSON.encodeToJsonElement(CommentBody.serializer(), CommentBody(body, references)),
            Comment.serializer(),
        )

    /** Replaces the body and the whole reference set. */
    suspend fun update(assetId: Int, commentId: Int, body: String, references: List<CommentReferenceIn> = emptyList()): Comment =
        http.sendJson(
            "PATCH", path(assetId, "/$commentId"),
            SDK_JSON.encodeToJsonElement(CommentBody.serializer(), CommentBody(body, references)),
            null, Comment.serializer(),
        )

    suspend fun delete(assetId: Int, commentId: Int) {
        http.sendJson("DELETE", path(assetId, "/$commentId"), null, null, Unit.serializer())
    }
}

class Documents internal constructor(private val http: Http, private val installationId: Int) {
    suspend fun list(assetId: Int): List<Document> =
        http.getJson(installationPath(installationId, "/assets/$assetId/documents"), null, ListSerializer(Document.serializer()))

    /**
     * Upload [file]. [filename] defaults to "document.pdf" when empty (the server rejects names without an
     * extension); [kind] is attachment | drawing | datasheet | manual | check_sheet | test_report; a client-minted
     * [uuid] makes retries idempotent.
     */
    suspend fun add(
        assetId: Int,
        file: File,
        filename: String = "",
        kind: String = "attachment",
        uuid: String? = null,
    ): Document =
        http.postFile(
            installationPath(installationId, "/assets/$assetId/documents"),
            listOf(MultipartFile("file", filename.ifEmpty { file.name }, file)),
            Document.serializer(),
            buildMap { put("kind", kind.ifEmpty { "attachment" }); uuid?.let { put("uuid", it) } },
        )

    suspend fun delete(assetId: Int, uuid: String) {
        requireUuid(uuid)
        http.sendJson("DELETE", installationPath(installationId, "/assets/$assetId/documents/$uuid"), null, null, Unit.serializer())
    }
}

/** Point alarm rules. Only method=threshold point overrides are writable; installation defaults are read-only (403). */
class AlarmRules internal constructor(private val http: Http, private val installationId: Int) {
    private fun path(pointId: Int, suffix: String = "") =
        installationPath(installationId, "/measurement-points/$pointId/alarm-rules$suffix")

    suspend fun list(pointId: Int): List<AlarmRule> =
        http.getJson(path(pointId), null, ListSerializer(AlarmRule.serializer()))

    /** 409 ([ConflictException]) if the point already has an override. */
    suspend fun create(
        pointId: Int,
        minorThreshold: Double,
        majorThreshold: Double,
        dataKey: String = "",
        direction: String = "high",
    ): AlarmRule =
        http.postJson(
            path(pointId),
            SDK_JSON.encodeToJsonElement(
                AlarmRuleCreate.serializer(),
                AlarmRuleCreate("threshold", dataKey, direction, minorThreshold, majorThreshold),
            ),
            AlarmRule.serializer(),
        )

    /** Only non-null arguments are sent. */
    suspend fun update(
        pointId: Int,
        uuid: String,
        minorThreshold: Double? = null,
        majorThreshold: Double? = null,
        dataKey: String? = null,
        direction: String? = null,
    ): AlarmRule {
        requireUuid(uuid)
        return http.sendJson(
            "PATCH", path(pointId, "/$uuid"),
            SDK_JSON.encodeToJsonElement(
                AlarmRulePatch.serializer(),
                AlarmRulePatch(dataKey, direction, minorThreshold, majorThreshold),
            ),
            null, AlarmRule.serializer(),
        )
    }

    suspend fun delete(pointId: Int, uuid: String) {
        requireUuid(uuid)
        http.sendJson("DELETE", path(pointId, "/$uuid"), null, null, Unit.serializer())
    }
}
