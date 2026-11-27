package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer

/** All resources scoped to a single installation. */
class Installation internal constructor(
    internal val http: Http,
    val installationId: Int,
) {
    val assets: Assets = Assets(http, installationId)
    val assetTypes: AssetTypes = AssetTypes(http, installationId)
    val measurementPoints: MeasurementPoints = MeasurementPoints(http, installationId)
    val measurements: Measurements = Measurements(http, installationId)
    val routes: Routes = Routes(http, installationId)
    val sections: Sections = Sections(http, installationId)
    val zones: Zones = Zones(http, installationId)
    val findings: Findings = Findings(http, installationId)
    val exports: Exports = Exports(http, installationId)
    val comments: Comments = Comments(http, installationId)
    val documents: Documents = Documents(http, installationId)
    val alarmRules: AlarmRules = AlarmRules(http, installationId)
    val devices: Devices = Devices(http, installationId)
    val sources: Sources = Sources(http, installationId)
    val dashboards: Dashboards = Dashboards(http, installationId)
    val analysis: Analysis = Analysis(http, installationId)
    val bearings: Bearings = Bearings(http, installationId)
    val nonConformities: NonConformities = NonConformities(http, installationId)

    suspend fun overview(): Overview = http.getJson(path("/overview"), null, Overview.serializer())

    /** Every asset needing attention, worst first then silent ones; [silentOnly] lists every silent asset instead. */
    suspend fun alerts(silentOnly: Boolean = false): List<Alert> =
        http.getJson(path("/alerts"), mapOf("show" to if (silentOnly) "silent" else null), ListSerializer(Alert.serializer()))

    /** The activity feed, newest first, [limit] (≤200) a page; [sectionId] narrows to one section. */
    suspend fun activity(cursor: String? = null, limit: Int? = null, sectionId: Int? = null): ActivityPage =
        http.getJson(
            path("/activity"),
            mapOf("cursor" to cursor, "limit" to limit, "section_id" to sectionId),
            ActivityPage.serializer(),
        )

    /** [q] under 2 characters finds nothing. [category] (a [SearchCategory.slug]) fills only that list, with more rows. */
    suspend fun search(q: String, category: String? = null): SearchResults =
        http.getJson(path("/search"), mapOf("q" to q, "in" to category), SearchResults.serializer())

    /** Running hours over local days (ISO dates, in `X-Timezone`); with neither, today. */
    suspend fun hours(productionFrom: String? = null, productionTo: String? = null): RunningHours =
        http.getJson(
            path("/hours"),
            mapOf("production_from" to productionFrom, "production_to" to productionTo),
            RunningHours.serializer(),
        )

    suspend fun notificationSettings(): NotificationSettings =
        http.getJson(path("/notification-settings"), null, NotificationSettings.serializer())

    /** Only non-null arguments are sent. [severityThreshold] is one of [NotificationSettings.thresholdChoices]. Service tokens 403. */
    suspend fun updateNotificationSettings(
        severityThreshold: Int? = null,
        statusChanges: Boolean? = null,
        routeCompletions: Boolean? = null,
        exports: Boolean? = null,
        notificationsMuted: Boolean? = null,
    ): NotificationSettings = http.sendJson(
        "PATCH", path("/notification-settings"),
        SDK_JSON.encodeToJsonElement(
            NotificationSettingsUpdate.serializer(),
            NotificationSettingsUpdate(severityThreshold, statusChanges, routeCompletions, exports, notificationsMuted),
        ),
        null, NotificationSettings.serializer(),
    )

    /** Send a test email now, muted or not. 422 without an email address; 502 ([ServerException]) when the provider refused it. */
    suspend fun testNotificationEmail(): EmailTestResult =
        http.postJson(path("/notification-settings/test"), null, EmailTestResult.serializer())

    private fun path(suffix: String) = installationPath(installationId, suffix)

    /** The legacy v1 QR URL → v2 measurement point map, for resolving old QR tags offline. Fetch once per sync and cache it. */
    suspend fun legacyRedirects(): List<LegacyRedirect> =
        http.getJson(installationPath(installationId, "/legacy-redirects"), null, LegacyRedirectsPage.serializer()).items
}

@Serializable
internal data class LegacyRedirectsPage(val items: List<LegacyRedirect>)

/** One legacy QR mapping: a v1 `/plantlayer|measurementpoint/<uuid>/` URL and the v2 measurement point it now is. */
@Serializable
data class LegacyRedirect(
    @SerialName("legacy_url") val legacyUrl: String,
    @SerialName("mp_uuid") val mpUuid: String,
    @SerialName("mp_path") val mpPath: String,
    @SerialName("installation_id") val installationId: Int,
    @SerialName("asset_id") val assetId: Int? = null,
    @SerialName("point_id") val pointId: Int? = null,
)

internal fun installationPath(installationId: Int, suffix: String): String =
    "/api/installations/$installationId$suffix"
