package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/** `legacyRedirects()` reads the v1 → v2 QR map (Swift parity). */
class LegacyRedirectsTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    @Test fun decodes_the_redirect_items() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
                """{"items":[{"legacy_url":"/measurementpoint/abc/","mp_uuid":"mp-1","mp_path":"/mp/mp-1",""" +
                    """"installation_id":2012,"asset_id":7,"point_id":null}]}""",
            ),
        )
        val out = client.forInstallation(2012).legacyRedirects()
        assertEquals("/api/installations/2012/legacy-redirects", server.takeRequest().path)
        assertEquals(listOf(LegacyRedirect("/measurementpoint/abc/", "mp-1", "/mp/mp-1", 2012, 7, null)), out)
    }
}
