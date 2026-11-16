package com.arpedon.mechbase

import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64
import kotlin.coroutines.cancellation.CancellationException
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import okhttp3.OkHttpClient

/**
 * Unauthenticated sign-in calls, made before there is a bearer token.
 *
 * ```kotlin
 * val auth = MechbaseAuth()                                  // or MechbaseAuth(selfHostedUrl)
 * if (auth.ssoCheck(email)) {                                // show "Sign in with Microsoft"
 *     val pkce = Pkce.generate()
 *     val url = auth.ssoStartUrl(pkce.challenge, loginHint = email)
 *     // open url in a Custom Tab, read `code` from the mechbase://sso?code=… callback, then:
 *     val token = auth.exchangeSsoCode(code, pkce.verifier, deviceId)
 *     val client = MechbaseClient(token = token)
 * }
 * ```
 */
class MechbaseAuth(
    baseUrl: String = MechbaseClient.DEFAULT_BASE_URL,
    okHttpClient: OkHttpClient = OkHttpClient(),
) {
    private val http = Http("", baseUrl, okHttpClient)

    /** Whether [email] signs in with Microsoft. Any error (network, 4xx/5xx, bad body) is `false`. */
    suspend fun ssoCheck(email: String): Boolean =
        try {
            http.getJson("/sso/check/", mapOf("email" to email), SsoCheck.serializer()).sso
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            false
        }

    /** The page that starts Microsoft sign-in; it ends on `mechbase://sso?code=…` (or `?error=…`). */
    fun ssoStartUrl(codeChallenge: String, loginHint: String? = null): String =
        http.buildUrl(
            "/sso/native/start/",
            mapOf("code_challenge" to codeChallenge, "code_challenge_method" to "S256", "login_hint" to loginHint),
        ).toString()

    /**
     * Trade the one-time [code] from the callback for a bearer token (single use).
     * Throws [AuthException] carrying the server's message on a rejected code
     * (400: expired, used, or a verifier that doesn't match).
     */
    suspend fun exchangeSsoCode(code: String, codeVerifier: String, deviceId: String? = null): String =
        try {
            http.postJson(
                "/api/auth/sso/exchange",
                SDK_JSON.encodeToJsonElement(ExchangeIn.serializer(), ExchangeIn(code, codeVerifier, deviceId)),
                TokenOut.serializer(),
            ).token
        } catch (e: ServerException) {
            if (e.status == 400) throw AuthException(e.message ?: "400", e.status, e.body)
            throw e
        }
}

/** A PKCE pair: send [challenge] to start sign-in, [verifier] to exchange the code. */
data class PkcePair(val verifier: String, val challenge: String)

/** RFC 7636 PKCE (S256). */
object Pkce {
    private val random = SecureRandom()
    private val b64url = Base64.getUrlEncoder().withoutPadding()

    /** A fresh verifier (32 random bytes, base64url, 43 chars) and its S256 challenge. */
    fun generate(): PkcePair {
        val bytes = ByteArray(32).also(random::nextBytes)
        val verifier = b64url.encodeToString(bytes)
        return PkcePair(verifier, challenge(verifier))
    }

    /** base64url(SHA-256(ASCII(verifier))), no padding. */
    fun challenge(verifier: String): String =
        b64url.encodeToString(MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII)))
}

@Serializable
private data class SsoCheck(val sso: Boolean = false)

@Serializable
private data class TokenOut(val token: String)

@Serializable
private data class ExchangeIn(
    val code: String,
    @SerialName("code_verifier") val codeVerifier: String,
    @SerialName("device_id") val deviceId: String? = null,
)
