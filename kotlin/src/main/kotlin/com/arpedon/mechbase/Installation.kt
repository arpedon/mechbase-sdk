package com.arpedon.mechbase

/** All resources scoped to a single installation. */
class Installation internal constructor(
    internal val http: Http,
    val installationId: Int,
) {
    val assets: Assets = Assets(http, installationId)
    val measurementPoints: MeasurementPoints = MeasurementPoints(http, installationId)
    val measurements: Measurements = Measurements(http, installationId)
    val routes: Routes = Routes(http, installationId)
}

internal fun installationPath(installationId: Int, suffix: String): String =
    "/api/installations/$installationId$suffix"
