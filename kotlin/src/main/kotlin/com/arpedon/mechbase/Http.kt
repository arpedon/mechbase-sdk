package com.arpedon.mechbase

import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response

internal val SDK_JSON: Json = Json {
    ignoreUnknownKeys = true
    encodeDefaults = false
    explicitNulls = false
    // Without this, a JSON `null` on a *non-nullable* property that has a
    // Kotlin default value (e.g. `Route.description: String = ""`) still
    // throws at decode time — defaults only apply to *absent* keys. The flag
    // extends the default to present-but-null values, which closes the long
    // tail of `TextField(blank=True, default="")` columns that may drift to
    // SQL NULL on a legacy row. It does nothing for non-nullable properties
    // that have no default — those must be made nullable in the model
    // (see issue #2).
    coerceInputValues = true
}

private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
private val OCTET_MEDIA = "application/octet-stream".toMediaType()

internal class Http(
    private val token: String,
    baseUrl: String,
    private val ok: OkHttpClient = OkHttpClient(),
    // Null: the JVM default zone, read per request so a device zone change is picked up.
    private val timeZone: String? = null,
) {
    private val baseUrl: String = baseUrl.trimEnd('/')

    internal fun buildUrl(path: String, params: Map<String, Any?>?, stripEmpty: Boolean = true): okhttp3.HttpUrl {
        val builder = (baseUrl + path).toHttpUrl().newBuilder()
        params?.forEach { (k, v) ->
            if (v == null) return@forEach
            val s = v.toString()
            if (stripEmpty && s.isEmpty()) return@forEach
            builder.addQueryParameter(k, s)
        }
        return builder.build()
    }

    private fun baseRequest(url: okhttp3.HttpUrl): Request.Builder =
        Request.Builder()
            .url(url)
            // Empty token: the unauthenticated sign-in calls (MechbaseAuth).
            .apply { if (token.isNotEmpty()) header("Authorization", "Bearer $token") }
            .header("User-Agent", "mechbase-kotlin/0.2")
            .header("Accept", "application/json")
            // Day windows (dashboard "today", hours, activity) follow it; the server ignores an invalid one.
            .header("X-Timezone", timeZone ?: java.time.ZoneId.systemDefault().id)

    suspend fun <T> getJson(
        path: String,
        params: Map<String, Any?>? = null,
        serializer: KSerializer<T>,
        stripEmpty: Boolean = true,
    ): T = withContext(Dispatchers.IO) {
        val request = baseRequest(buildUrl(path, params, stripEmpty)).get().build()
        ok.newCall(request).execute().use { resp ->
            val body = handle(resp)
            SDK_JSON.decodeFromString(serializer, body)
        }
    }

    /** GET with `If-None-Match`; a 304 is [Conditional.NotModified], else the body and its (verbatim) ETag. */
    suspend fun <T> getConditional(
        path: String,
        params: Map<String, Any?>?,
        serializer: KSerializer<T>,
        ifNoneMatch: String?,
    ): Conditional<T> = withContext(Dispatchers.IO) {
        val builder = baseRequest(buildUrl(path, params)).get()
        ifNoneMatch?.let { builder.header("If-None-Match", it) }
        ok.newCall(builder.build()).execute().use { resp ->
            if (resp.code == 304) return@use Conditional.NotModified
            val body = handle(resp)
            Conditional.Fresh(SDK_JSON.decodeFromString(serializer, body), resp.header("ETag"))
        }
    }

    suspend fun getBytes(path: String, params: Map<String, Any?>? = null): ByteArray = withContext(Dispatchers.IO) {
        val request = baseRequest(buildUrl(path, params)).header("Accept", "*/*").get().build()
        ok.newCall(request).execute().use { resp ->
            if (resp.code in 200..299) resp.body?.bytes() ?: ByteArray(0) else handle(resp).let { ByteArray(0) }
        }
    }

    suspend fun <T> postJson(
        path: String,
        payload: JsonElement?,
        serializer: KSerializer<T>,
        headers: Map<String, String> = emptyMap(),
    ): T = withContext(Dispatchers.IO) {
        val bodyStr = if (payload == null) "" else SDK_JSON.encodeToString(JsonElement.serializer(), payload)
        val rb: RequestBody = bodyStr.toRequestBody(JSON_MEDIA)
        val builder = baseRequest(buildUrl(path, null)).post(rb)
        headers.forEach { (k, v) -> builder.header(k, v) }
        val request = builder.build()
        ok.newCall(request).execute().use { resp ->
            val body = handle(resp)
            if (body.isEmpty()) {
                @Suppress("UNCHECKED_CAST")
                Unit as T
            } else {
                SDK_JSON.decodeFromString(serializer, body)
            }
        }
    }

    suspend fun <T> sendJson(
        method: String,
        path: String,
        payload: JsonElement?,
        params: Map<String, Any?>? = null,
        serializer: KSerializer<T>,
    ): T = withContext(Dispatchers.IO) {
        val rb: RequestBody? = payload?.let {
            SDK_JSON.encodeToString(JsonElement.serializer(), it).toRequestBody(JSON_MEDIA)
        }
        val builder = baseRequest(buildUrl(path, params))
        val request = when (method) {
            "PUT" -> builder.put(rb ?: "".toRequestBody(JSON_MEDIA))
            "PATCH" -> builder.patch(rb ?: "".toRequestBody(JSON_MEDIA))
            "DELETE" -> if (rb != null) builder.delete(rb) else builder.delete()
            else -> error("unsupported method $method")
        }.build()
        ok.newCall(request).execute().use { resp ->
            val body = handle(resp)
            if (body.isEmpty()) {
                @Suppress("UNCHECKED_CAST")
                Unit as T
            } else {
                SDK_JSON.decodeFromString(serializer, body)
            }
        }
    }

    suspend fun <T> postMultipart(
        path: String,
        payload: JsonObject,
        files: List<MultipartFile>,
        serializer: KSerializer<T>,
        headers: Map<String, String> = emptyMap(),
    ): T = withContext(Dispatchers.IO) {
        val payloadStr = SDK_JSON.encodeToString(JsonObject.serializer(), payload)
        val mb = MultipartBody.Builder().setType(MultipartBody.FORM)
        mb.addFormDataPart("payload", payloadStr)
        files.forEach { mf ->
            mb.addFormDataPart(
                mf.fieldName,
                mf.filename,
                mf.file.asRequestBody(OCTET_MEDIA),
            )
        }
        val builder = baseRequest(buildUrl(path, null)).post(mb.build())
        headers.forEach { (k, v) -> builder.header(k, v) }
        val request = builder.build()
        ok.newCall(request).execute().use { resp ->
            val body = handle(resp)
            SDK_JSON.decodeFromString(serializer, body)
        }
    }

    suspend fun <T> postFile(
        path: String,
        files: List<MultipartFile>,
        serializer: KSerializer<T>,
        fields: Map<String, String> = emptyMap(),
        headers: Map<String, String> = emptyMap(),
    ): T = withContext(Dispatchers.IO) {
        val mb = MultipartBody.Builder().setType(MultipartBody.FORM)
        fields.forEach { (k, v) -> mb.addFormDataPart(k, v) }
        files.forEach { mf -> mb.addFormDataPart(mf.fieldName, mf.filename, mf.file.asRequestBody(OCTET_MEDIA)) }
        val builder = baseRequest(buildUrl(path, null)).post(mb.build())
        headers.forEach { (k, v) -> builder.header(k, v) }
        ok.newCall(builder.build()).execute().use { resp -> SDK_JSON.decodeFromString(serializer, handle(resp)) }
    }

    private fun handle(resp: Response): String {
        val code = resp.code
        val text = resp.body?.string().orEmpty()
        if (code == 204) return ""
        if (code in 200..299) return text

        val detail = runCatching {
            val parsed = SDK_JSON.parseToJsonElement(text)
            (parsed as? JsonObject)?.let { it["detail"] ?: it["error"] }?.jsonPrimitive?.content
        }.getOrNull() ?: text
        val message = "$code $detail"
        throw when (code) {
            401, 403 -> AuthException(message, code, text)
            404 -> NotFoundException(message, code, text)
            409 -> ConflictException(message, code, text)
            413 -> PayloadTooLargeException(message, code, text)
            422 -> ValidationException(message, code, text)
            else -> ServerException(message, code, text)
        }
    }
}

internal data class MultipartFile(
    val fieldName: String,
    val filename: String,
    val file: File,
)
