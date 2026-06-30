package com.arpedon.mechbase

import java.io.File
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/**
 * `X-Idempotency-Key` parity with the Swift SDK: `measurements.create` and
 * `execution.respond` emit the header only when an `idempotencyKey` is supplied,
 * on both the JSON and multipart variants. With no key the request is unchanged
 * (no header). See A2 / mechbase-web#190.
 */
class MeasurementIdempotencyTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    private fun enqueueMeasurement() = server.enqueue(
        MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"m1","measurement_point_id":5,"point_sequence":1,"data":{"rms":1.2},""" +
                """"status":"good","notes":"","created_at":"2026-01-01T00:00:00Z","file_url":null}""",
        ),
    )

    private fun enqueueExecution() = server.enqueue(
        MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"exec-1","route_uuid":"r-1","status":"in_progress",""" +
                """"started_at":"2026-01-01T00:00:00Z","completed_at":null,"session_id":"s-1"}""",
        ),
    )

    private fun enqueueResponse() = server.enqueue(
        MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"resp-1","route_item_uuid":"item-1","data":{"passed":true},""" +
                """"notes":"","status":1,"created_at":"2026-01-01T00:00:01Z"}""",
        ),
    )

    private fun tempFile(name: String): File =
        File.createTempFile("idem-$name", ".bin").apply { writeBytes(byteArrayOf(0, 1, 2, 3)) }

    @Test fun create_json_sends_idempotency_header() = runBlocking {
        enqueueMeasurement()
        client.forInstallation(2012).measurements.create(
            pointId = 5, data = mapOf("rms" to 1.2), idempotencyKey = "k",
        )
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/measurements/", rec.path)
        assertEquals("k", rec.getHeader("X-Idempotency-Key"))
    }

    @Test fun create_multipart_sends_idempotency_header() = runBlocking {
        enqueueMeasurement()
        client.forInstallation(2012).measurements.create(
            pointId = 5, data = mapOf("rms" to 1.2), file = tempFile("c"), idempotencyKey = "k",
        )
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/measurements/upload/", rec.path)
        assertEquals("k", rec.getHeader("X-Idempotency-Key"))
    }

    @Test fun respond_json_sends_idempotency_header() = runBlocking {
        enqueueExecution(); enqueueResponse()
        val exec = client.forInstallation(2012).routes.start("r-1")
        exec.respond(routeItemUUID = "item-1", data = mapOf("passed" to true), idempotencyKey = "k")
        server.takeRequest() // start
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/executions/exec-1/responses", rec.path)
        assertEquals("k", rec.getHeader("X-Idempotency-Key"))
    }

    @Test fun respond_multipart_sends_idempotency_header() = runBlocking {
        enqueueExecution(); enqueueResponse()
        val exec = client.forInstallation(2012).routes.start("r-1")
        exec.respond(
            routeItemUUID = "item-1", data = mapOf("passed" to true),
            photos = listOf(tempFile("p")), idempotencyKey = "k",
        )
        server.takeRequest() // start
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/executions/exec-1/responses/upload", rec.path)
        assertEquals("k", rec.getHeader("X-Idempotency-Key"))
    }

    @Test fun create_without_key_sends_no_header() = runBlocking {
        enqueueMeasurement()
        client.forInstallation(2012).measurements.create(pointId = 5, data = mapOf("rms" to 1.2))
        val rec = server.takeRequest()
        assertNull("no key supplied → header must be absent", rec.getHeader("X-Idempotency-Key"))
    }
}
