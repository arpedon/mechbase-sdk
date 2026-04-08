package com.arpedon.mechbase

import okhttp3.OkHttpClient

/**
 * Top-level Mechbase client.
 *
 * ```kotlin
 * val client = MechbaseClient(token = "...", baseUrl = "https://mechbase.arpedon.com")
 * val me = client.me()
 * val installation = client.forInstallation(me.currentInstallationId)
 * ```
 */
class MechbaseClient(
    token: String,
    baseUrl: String = "https://mechbase.arpedon.com",
    okHttpClient: OkHttpClient = OkHttpClient(),
) {
    internal val http: Http = Http(token, baseUrl, okHttpClient)

    suspend fun me(): Me =
        http.getJson("/api/me", null, Me.serializer())

    fun forInstallation(installationId: Int): Installation =
        Installation(http, installationId)
}
