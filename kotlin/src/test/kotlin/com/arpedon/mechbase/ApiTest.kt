package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Before

/** MockWebServer plumbing shared by the parity tests. */
abstract class ApiTest {
    protected lateinit var server: MockWebServer
    protected lateinit var client: MechbaseClient
    protected val inst get() = client.forInstallation(7)

    protected val u1 = "11111111-1111-4111-8111-111111111111"
    protected val u2 = "22222222-2222-4222-8222-222222222222"
    protected val u3 = "33333333-3333-4333-8333-333333333333"

    @Before fun setUpServer() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'), timeZone = "Europe/Athens")
    }

    @After fun tearDownServer() { server.shutdown() }

    protected fun json(body: String, code: Int = 200): MockResponse =
        MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    protected fun reply(body: String, code: Int = 200) = server.enqueue(json(body, code))

    protected fun noContent() = server.enqueue(MockResponse().setResponseCode(204))

    /** The next request as "METHOD /path?query", plus the request itself. */
    protected fun take(): RecordedRequest = server.takeRequest()

    protected fun RecordedRequest.line() = "$method $path"

    protected fun assertRequest(expected: String, body: String? = null): RecordedRequest {
        val r = take()
        assertEquals(expected, r.line())
        if (body != null) assertEquals(body, r.body.readUtf8())
        return r
    }

    protected inline fun <reified T : Throwable> assertFails(code: Int, crossinline call: suspend () -> Unit): T {
        reply("""{"detail":"nope"}""", code)
        val e = assertThrows(T::class.java) { runBlocking { call() } }
        take()
        return e
    }
}
