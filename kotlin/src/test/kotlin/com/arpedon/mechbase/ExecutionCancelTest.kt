package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** `Execution.cancel` hits the cancel endpoint; a 409 (run has answers) surfaces as [ConflictException]. */
class ExecutionCancelTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    @Test fun cancel_posts_to_the_cancel_endpoint() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
                """{"uuid":"exec-1","route_uuid":"route-1","status":"cancelled",""" +
                    """"started_at":"2026-11-15T08:30:00Z","completed_at":null,"session_id":"sess-1"}""",
            ),
        )

        val result = client.forInstallation(2012).routes.execution("exec-1").cancel()

        assertEquals("cancelled", result.status)
        val rec = server.takeRequest()
        assertEquals("POST", rec.method)
        assertEquals("/api/installations/2012/executions/exec-1/cancel", rec.path)
    }

    @Test fun cancel_on_a_run_with_answers_throws_conflict() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(409).setBody("""{"detail":"Execution has responses."}"""))

        val thrown = runCatching { client.forInstallation(2012).routes.execution("exec-1").cancel() }.exceptionOrNull()

        assertTrue("expected ConflictException, got $thrown", thrown is ConflictException)
    }
}
