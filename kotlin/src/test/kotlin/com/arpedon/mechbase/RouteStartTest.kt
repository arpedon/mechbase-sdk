package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * `Routes.start` body shape: offline-first clients pass a client-minted `uuid`
 * (and the real field `started_at`) so a queued start can be pushed and the
 * server upserts on it; bare callers keep the legacy empty POST. See issue #11.
 */
class RouteStartTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    private fun executionBody(uuid: String, routeUuid: String) =
        """{"uuid":"$uuid","route_uuid":"$routeUuid","status":"in_progress",""" +
            """"started_at":"2026-06-22T08:30:00Z","completed_at":null,"session_id":"sess-1"}"""

    @Test fun start_with_client_uuid_and_startedAt_sends_them_in_body() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(201)
                .setHeader("Content-Type", "application/json")
                .setBody(executionBody("exec-1", "route-1")),
        )

        val exec = client.forInstallation(2012).routes.start(
            routeUUID = "route-1",
            uuid = "exec-1",
            startedAt = "2026-06-22T08:30:00Z",
        )
        assertEquals("exec-1", exec.uuid)

        val rec = server.takeRequest()
        assertEquals("POST", rec.method)
        assertEquals("/api/installations/2012/routes/route-1/executions", rec.path)
        val body = rec.body.readUtf8()
        assertTrue("body should carry the client uuid, was $body", body.contains("\"uuid\":\"exec-1\""))
        assertTrue("body should carry started_at, was $body", body.contains("\"started_at\":\"2026-06-22T08:30:00Z\""))
    }

    @Test fun start_without_args_posts_an_empty_body() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(201)
                .setHeader("Content-Type", "application/json")
                .setBody(executionBody("server-exec", "route-1")),
        )

        client.forInstallation(2012).routes.start("route-1")

        val rec = server.takeRequest()
        assertEquals("POST", rec.method)
        assertEquals("/api/installations/2012/routes/route-1/executions", rec.path)
        assertEquals("bare start is the legacy empty POST (server mints the uuid)", "", rec.body.readUtf8())
    }

    @Test fun conflict_exposes_the_running_execution_and_it_can_be_fetched() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(409).setHeader("Content-Type", "application/json")
                .setBody("""{"detail":"Route already running","running_execution_uuid":"run-9"}"""),
        )
        server.enqueue(
            MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json")
                .setBody(executionBody("run-9", "route-1")),
        )
        val routes = client.forInstallation(2012).routes
        val conflict = runCatching { routes.start("route-1", uuid = "mine") }.exceptionOrNull() as ConflictException
        assertEquals("run-9", conflict.runningExecutionUuid)

        val running = routes.fetchExecution(conflict.runningExecutionUuid!!)
        assertEquals("run-9", running.uuid)
        server.takeRequest()
        assertEquals("/api/installations/2012/executions/run-9", server.takeRequest().path)
        assertEquals(null, ConflictException("x", 409, "not json").runningExecutionUuid)
        // The other start 409 (uuid already on another route) sends an explicit null.
        assertEquals(null, ConflictException("x", 409, """{"detail":"d","running_execution_uuid":null}""").runningExecutionUuid)
    }
}
