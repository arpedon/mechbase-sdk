@file:JvmName("PushMeasurementExample")

package com.arpedon.mechbase.examples

import com.arpedon.mechbase.MechbaseClient
import kotlinx.coroutines.runBlocking

fun main() = runBlocking {
    val token = System.getenv("MECHBASE_TOKEN")
        ?: error("Set MECHBASE_TOKEN")
    val baseUrl = System.getenv("MECHBASE_URL") ?: MechbaseClient.DEFAULT_BASE_URL

    val client = MechbaseClient(token = token, baseUrl = baseUrl)
    val me = client.me()
    val installation = client.forInstallation(me.currentInstallationId)

    val points = installation.measurementPoints.list(transducerType = "VB", limit = 1)
    val point = points.firstOrNull() ?: error("No VB measurement points found")
    val pointId = point.pointId ?: error("Point has no numeric id")

    val measurement = installation.measurements.create(
        pointId = pointId,
        data = mapOf("rms" to 2.3, "peak" to 5.1),
        notes = "pushed from kotlin example",
    )

    @Suppress("ForbiddenMethodCall")
    System.out.println("Created measurement ${measurement.uuid} seq=${measurement.pointSequence}")
}
