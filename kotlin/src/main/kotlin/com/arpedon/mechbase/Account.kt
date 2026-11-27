package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Units to change in [MechbaseClient.updateMe]; null keeps a unit. Values as `/api/me/` returns them (e.g. `"mm/s"`). */
@Serializable
data class UnitPrefsUpdate(
    val acceleration: String? = null,
    val velocity: String? = null,
    val temperature: String? = null,
    val pressure: String? = null,
    val frequency: String? = null,
)

@Serializable
internal data class MeUpdate(
    @SerialName("first_name") val firstName: String? = null,
    @SerialName("last_name") val lastName: String? = null,
    @SerialName("unit_prefs") val unitPrefs: UnitPrefsUpdate? = null,
)

@Serializable
internal data class PushDeviceBody(
    val platform: String,
    val token: String,
    @SerialName("app_version") val appVersion: String,
)

@Serializable
data class PushDevice(
    val platform: String = "",
    val token: String = "",
    @SerialName("app_version") val appVersion: String = "",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("last_seen_at") val lastSeenAt: String = "",
)

@Serializable
internal data class WebSessionBody(val next: String)

/** A one-time browser sign-in link from [MechbaseClient.webSession]: open [url] once, within the minute. */
@Serializable
data class WebSession(
    val url: String,
    @SerialName("expires_at") val expiresAt: String = "",
)
