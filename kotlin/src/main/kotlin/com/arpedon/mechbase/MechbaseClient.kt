package com.arpedon.mechbase

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
 */
class MechbaseClient(
    token: String,
    baseUrl: String = DEFAULT_BASE_URL,
    okHttpClient: OkHttpClient = OkHttpClient(),
) {
    internal val http: Http = Http(token, baseUrl, okHttpClient)

    suspend fun me(): Me =
        http.getJson("/api/me/", null, Me.serializer())

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
