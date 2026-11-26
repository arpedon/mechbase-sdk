package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

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
