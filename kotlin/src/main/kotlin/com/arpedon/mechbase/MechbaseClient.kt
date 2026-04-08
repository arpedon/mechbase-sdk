package com.arpedon.mechbase

import okhttp3.OkHttpClient

/**
 * Top-level Mechbase client.
 *
 * ```kotlin
 * val client = MechbaseClient(token = "...")  // defaults to https://app.mechbase.io
 * val me = client.me()
 * val installation = client.forInstallation(me.currentInstallationId)
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
        http.getJson("/api/me", null, Me.serializer())

    fun forInstallation(installationId: Int): Installation =
        Installation(http, installationId)

    companion object {
        const val DEFAULT_BASE_URL: String = "https://app.mechbase.io"
    }
}
