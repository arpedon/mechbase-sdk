package com.arpedon.mechbase

import java.net.URLEncoder
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.JsonElement
import okhttp3.OkHttpClient

/**
 * Top-level Mechbase client.
 *
 * ```kotlin
 * val client = MechbaseClient(token = "...")  // defaults to https://app.mechbase.io
 * val me = client.me()
 * val installation = client.forInstallation(me.currentInstallationId ?: error("This user has no installation"))
 * ```
 *
 * For self-hosted installations pass an explicit `baseUrl`.
 *
 * Every request sends `X-Timezone` (day windows such as the dashboard's "today" follow it): the
 * JVM default zone, read per request, unless [timeZone] pins an IANA id such as `"Europe/Athens"`.
 */
class MechbaseClient(
    token: String,
    baseUrl: String = DEFAULT_BASE_URL,
    okHttpClient: OkHttpClient = OkHttpClient(),
    timeZone: String? = null,
) {
    internal val http: Http = Http(token, baseUrl, okHttpClient, timeZone)

    suspend fun me(): Me =
        http.getJson("/api/me/", null, Me.serializer())

    /**
     * Change the signed-in user's name and display units. Only non-null arguments are sent (the
     * server validates just those); a [UnitPrefsUpdate] sends only its non-null units.
     */
    suspend fun updateMe(
        firstName: String? = null,
        lastName: String? = null,
        unitPrefs: UnitPrefsUpdate? = null,
    ): Me = http.sendJson(
        "PATCH", "/api/me/",
        SDK_JSON.encodeToJsonElement(MeUpdate.serializer(), MeUpdate(firstName, lastName, unitPrefs)),
        null, Me.serializer(),
    )

    /**
     * Register this device for push after sign-in and on every token refresh (upsert by [token]).
     * [platform] is `apns` (hex token) or `fcm`. The registration lives as long as this API token.
     */
    suspend fun registerPushDevice(platform: String, token: String, appVersion: String = ""): PushDevice =
        http.postJson(
            "/api/push/devices",
            SDK_JSON.encodeToJsonElement(PushDeviceBody.serializer(), PushDeviceBody(platform, token, appVersion)),
            PushDevice.serializer(),
        )

    /** Drop a push registration on sign-out (best effort). An unknown [token] throws [NotFoundException]. */
    suspend fun deletePushDevice(token: String) {
        // Percent-encoded into one path segment, so a token can't reroute the DELETE.
        val segment = URLEncoder.encode(token, "UTF-8").replace("+", "%20")
        http.sendJson("DELETE", "/api/push/devices/$segment", null, null, Unit.serializer())
    }

    /**
     * A single-use, 60-second link that signs an in-app browser (Custom Tab) in as this token's user
     * and opens [next], so the web doesn't ask for a password again. [next] is a server path
     * (`/2012/assets/5/`) or the `https://` URL of a device tunnel the user can open; anything else
     * throws [ValidationException]. Service and installation-scoped tokens get [AuthException].
     * Mint it right before opening; never cache it.
     */
    suspend fun webSession(next: String): WebSession =
        http.postJson(
            "/api/auth/web-session",
            SDK_JSON.encodeToJsonElement(WebSessionBody.serializer(), WebSessionBody(next)),
            WebSession.serializer(),
        )

    /** Sign this token out server-side. The token is dead afterwards; drop it. */
    suspend fun revokeToken() {
        http.postJson("/api/auth/token/revoke", null, JsonElement.serializer())
    }

    /** Every installation's tunnels (staff only). */
    suspend fun tunnels(): List<Tunnel> =
        http.getJson("/api/tunnels", null, kotlinx.serialization.builtins.ListSerializer(Tunnel.serializer()))

    /** An stcp tunnel's frpc config (staff only): `frpc -c <file>`, then 127.0.0.1:<localPort>. It holds secrets. */
    suspend fun tunnelVisitorFile(tunnelUuid: String): ByteArray {
        requireUuid(tunnelUuid)
        return http.getBytes("/api/tunnels/$tunnelUuid/visitor.toml")
    }

    fun forInstallation(installationId: Int): Installation =
        Installation(http, installationId)

    companion object {
        const val DEFAULT_BASE_URL: String = "https://app.mechbase.io"
    }
}
