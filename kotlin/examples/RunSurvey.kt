@file:JvmName("RunSurveyExample")

package com.arpedon.mechbase.examples

import com.arpedon.mechbase.MechbaseClient
import kotlinx.coroutines.runBlocking

fun main() = runBlocking {
    val token = System.getenv("MECHBASE_TOKEN") ?: error("Set MECHBASE_TOKEN")
    val baseUrl = System.getenv("MECHBASE_URL") ?: "https://mechbase.arpedon.com"
    val routeUuid = System.getenv("ROUTE_UUID") ?: error("Set ROUTE_UUID")

    val client = MechbaseClient(token = token, baseUrl = baseUrl)
    val me = client.me()
    val installation = client.forInstallation(me.currentInstallationId)

    val execution = installation.routes.start(routeUUID = routeUuid)
    @Suppress("ForbiddenMethodCall")
    System.out.println("Started execution ${execution.uuid}")

    execution.addFieldItem(
        label = "Oil leak observed near coupling",
        itemType = "pass_fail",
        data = mapOf("passed" to false, "severity" to "major"),
    )

    val finished = execution.complete()
    @Suppress("ForbiddenMethodCall")
    System.out.println("Completed execution status=${finished.status}")
}
