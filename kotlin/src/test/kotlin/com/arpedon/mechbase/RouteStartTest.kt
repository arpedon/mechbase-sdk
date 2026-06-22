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
}
