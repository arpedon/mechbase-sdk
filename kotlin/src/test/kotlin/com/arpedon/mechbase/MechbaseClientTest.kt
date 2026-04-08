package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

class MechbaseClientTest {

    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun me() = runBlocking {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody(
                    """
                    {
                      "user": {"id": 1, "username": "u", "full_name": "U U", "email": "u@u"},
                      "installations": [{"installation_id": 2012, "name": "Plant"}],
                      "current_installation_id": 2012
                    }
                    """.trimIndent()
                )
        )
        val me = client.me()
        assertEquals("u", me.user.username)
        assertEquals(2012, me.currentInstallationId)
        assertEquals("Plant", me.installations[0].name)

        val recorded = server.takeRequest()
        assertEquals("/api/me/", recorded.path)
        assertEquals("Bearer tok", recorded.getHeader("Authorization"))
        assertEquals("mechbase-kotlin/0.1", recorded.getHeader("User-Agent"))
    }

    @Test
    fun listAssets() = runBlocking {
        server.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setHeader("Content-Type", "application/json")
                .setBody(
                    """
                    {
                      "items": [
                        {
                          "uuid": "00000000-0000-0000-0000-000000000001",
                          "asset_id": 1,
                          "name": "Pump 1",
                          "zone_id": 1,
                          "machine_class": "II",
                          "status": 1
                        }
                      ],
                      "total": 1, "limit": 50, "offset": 0
                    }
                    """.trimIndent()
                )
        )
        val assets = client.forInstallation(2012).assets.list()
        assertEquals(1, assets.size)
        assertEquals("Pump 1", assets[0].name)

        val recorded = server.takeRequest()
        assertTrue(recorded.path!!.startsWith("/api/installations/2012/assets"))
    }

    @Test
    fun createMeasurement() = runBlocking {
        server.enqueue(
            MockResponse()
                .setResponseCode(201)
                .setHeader("Content-Type", "application/json")
                .setBody(
                    """
                    {
                      "uuid": "00000000-0000-0000-0000-000000000002",
                      "measurement_point_id": 1,
                      "point_sequence": 5,
                      "data": {"rms": 2.3},
                      "status": "good",
                      "notes": "",
                      "created_at": "2026-04-08T10:00:00Z",
                      "file_url": null
                    }
                    """.trimIndent()
                )
        )
        val m = client.forInstallation(2012)
            .measurements.create(pointId = 1, data = mapOf("rms" to 2.3))
        assertEquals(5, m.pointSequence)
        assertEquals("good", m.status)

        val recorded = server.takeRequest()
        assertEquals("/api/installations/2012/measurements/", recorded.path)
        assertEquals("POST", recorded.method)
        val body = recorded.body.readUtf8()
        assertTrue(body.contains("\"measurement_point_id\":1"))
        assertTrue(body.contains("\"rms\":2.3"))
    }

    @Test
    fun startExecutionAndRespond() = runBlocking {
        server.enqueue(
            MockResponse()
                .setResponseCode(201)
                .setHeader("Content-Type", "application/json")
                .setBody(
                    """
                    {
                      "uuid": "exec-uuid",
                      "route_uuid": "r-uuid",
                      "status": "in_progress",
                      "started_at": "2026-04-08T10:00:00Z",
                      "completed_at": null,
                      "session_id": "sess-uuid"
                    }
                    """.trimIndent()
                )
        )
        server.enqueue(
            MockResponse()
                .setResponseCode(201)
                .setHeader("Content-Type", "application/json")
                .setBody(
                    """
                    {
                      "uuid": "resp-uuid",
                      "route_item_uuid": "item-uuid",
                      "data": {"passed": true},
                      "notes": "",
                      "status": 1,
                      "created_at": "2026-04-08T10:00:01Z"
                    }
                    """.trimIndent()
                )
        )
        val execution = client.forInstallation(2012).routes.start("r-uuid")
        assertEquals("exec-uuid", execution.uuid)
        val resp = execution.respond(routeItemUUID = "item-uuid", data = mapOf("passed" to true))
        assertEquals(1, resp.status)
        assertNotNull(execution.execution)

        val req1 = server.takeRequest()
        assertEquals("/api/installations/2012/routes/r-uuid/executions", req1.path)
        val req2 = server.takeRequest()
        assertEquals("/api/installations/2012/executions/exec-uuid/responses", req2.path)
    }

    @Test
    fun authErrorRaises() = runBlocking {
        server.enqueue(
            MockResponse()
                .setResponseCode(401)
                .setHeader("Content-Type", "application/json")
                .setBody("""{"detail": "nope"}""")
        )
        try {
            client.me()
            fail("expected AuthException")
        } catch (e: AuthException) {
            assertEquals(401, e.status)
        }
    }
}
