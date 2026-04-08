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
}

private val JSON_MEDIA = "application/json; charset=utf-8".toMediaType()
private val OCTET_MEDIA = "application/octet-stream".toMediaType()

internal class Http(
    private val token: String,
    baseUrl: String,
    private val ok: OkHttpClient = OkHttpClient(),
) {
    private val baseUrl: String = baseUrl.trimEnd('/')

    private fun buildUrl(path: String, params: Map<String, Any?>?): okhttp3.HttpUrl {
        val builder = (baseUrl + path).toHttpUrl().newBuilder()
        params?.forEach { (k, v) ->
            if (v == null) return@forEach
            val s = v.toString()
            if (s.isEmpty()) return@forEach
            builder.addQueryParameter(k, s)
        }
        return builder.build()
    }

    private fun baseRequest(url: okhttp3.HttpUrl): Request.Builder =
        Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $token")
            .header("User-Agent", "mechbase-kotlin/0.1")
            .header("Accept", "application/json")

    suspend fun <T> getJson(
        path: String,
        params: Map<String, Any?>? = null,
        serializer: KSerializer<T>,
    ): T = withContext(Dispatchers.IO) {
        val request = baseRequest(buildUrl(path, params)).get().build()
        ok.newCall(request).execute().use { resp ->
            val body = handle(resp)
            SDK_JSON.decodeFromString(serializer, body)
        }
    }

    suspend fun <T> postJson(
        path: String,
        payload: JsonElement?,
        serializer: KSerializer<T>,
    ): T = withContext(Dispatchers.IO) {
        val bodyStr = if (payload == null) "" else SDK_JSON.encodeToString(JsonElement.serializer(), payload)
        val rb: RequestBody = bodyStr.toRequestBody(JSON_MEDIA)
        val request = baseRequest(buildUrl(path, null)).post(rb).build()
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
        val request = baseRequest(buildUrl(path, null)).post(mb.build()).build()
        ok.newCall(request).execute().use { resp ->
            val body = handle(resp)
            SDK_JSON.decodeFromString(serializer, body)
        }
    }

    private fun handle(resp: Response): String {
        val code = resp.code
        val text = resp.body?.string().orEmpty()
        if (code == 204) return ""
        if (code in 200..299) return text

        val detail = runCatching {
            val parsed = SDK_JSON.parseToJsonElement(text)
            (parsed as? JsonObject)?.get("detail")?.jsonPrimitive?.content
        }.getOrNull() ?: text
        val message = "$code $detail"
        throw when (code) {
            401, 403 -> AuthException(message, code, text)
            404 -> NotFoundException(message, code, text)
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
