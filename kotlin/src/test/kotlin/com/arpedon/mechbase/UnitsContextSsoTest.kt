package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/** Unit prefs on `me`, display units on points, point context, and Microsoft sign-in (Swift parity). */
class UnitsContextSsoTest {
    private lateinit var server: MockWebServer
    private lateinit var base: String
    private val client get() = MechbaseClient(token = "tok", baseUrl = base)
    private val auth get() = MechbaseAuth(base)

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        base = server.url("/").toString().trimEnd('/')
    }
    @After fun tearDown() { server.shutdown() }

    private fun reply(body: String, code: Int = 200) =
        server.enqueue(MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body))

    private val user = """"user":{"id":1,"username":"u","full_name":"U","email":"u@x.io"},"installations":[],"current_installation_id":null"""
    private val point = """"uuid":"p","point_id":5,"name":"DE","asset_id":3,"transducer_type":"temp","measurement_unit_code":"c","location":"","status":1"""

    @Test fun me_decodes_unit_prefs() = runBlocking {
        reply("""{$user,"unit_prefs":{"acceleration":"g","velocity":"in/s","temperature":"°F","pressure":"psi","frequency":"CPM"}}""")
        assertEquals(UnitPrefs("g", "in/s", "°F", "psi", "CPM"), client.me().unitPrefs)
    }

    @Test fun me_without_unit_prefs_is_null() = runBlocking {
        reply("{$user}")
        assertNull(client.me().unitPrefs)
    }

    @Test fun point_decodes_display_units_and_converts() = runBlocking {
        reply("""{$point,"display_units":{"value":{"native":"°C","unit":"°F","scale":1.8,"offset":32.0}}}""")
        val du = client.forInstallation(7).measurementPoints.get(5).displayUnits.getValue("value")
        assertEquals(DisplayUnit("°C", "°F", 1.8, 32.0), du)
        assertEquals(212.0, du.convert(100.0), 1e-9)
    }

    @Test fun point_without_display_units_is_empty() = runBlocking {
        reply("{$point}")
        assertEquals(emptyMap<String, DisplayUnit>(), client.forInstallation(7).measurementPoints.get(5).displayUnits)
    }

    @Test fun context_decodes_full_body() = runBlocking {
        reply(
            """{"data_key":"rms","unit":"mm/s","running":true,"running_at":"2026-11-16T09:12:00Z","stale_since":"2026-11-15T00:00:00Z",""" +
                """"limits":{"minor":4.5,"major":7.1},"week":[{"t":"2026-11-09T12:00:00Z","v":2.31},{"t":"2026-11-09T18:00:00Z","v":2.5}]}""",
        )
        val ctx = client.forInstallation(7).measurementPoints.context(5)
        assertEquals("/api/installations/7/measurement-points/5/context", server.takeRequest().path)
        assertEquals(
            PointContext(
                "rms", "mm/s", true, "2026-11-16T09:12:00Z", "2026-11-15T00:00:00Z", PointLimits(4.5, 7.1),
                listOf(TrendBin("2026-11-09T12:00:00Z", 2.31), TrendBin("2026-11-09T18:00:00Z", 2.5)),
            ),
            ctx,
        )
    }

    @Test fun context_decodes_nulls() = runBlocking {
        reply("""{"data_key":"value","unit":"°C","running":null,"running_at":null,"stale_since":null,"limits":null,"week":[]}""")
        assertEquals(PointContext("value", "°C"), client.forInstallation(7).measurementPoints.context(5))
    }

    @Test fun pkce_known_answer_rfc7636() {
        assertEquals("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", Pkce.challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"))
    }

    @Test fun pkce_generate() {
        val a = Pkce.generate()
        assertEquals(43, a.verifier.length)
        assertEquals(43, a.challenge.length)
        assertFalse(a.verifier.any { it in "+/=" })
        assertEquals(Pkce.challenge(a.verifier), a.challenge)
        assertNotEquals(a.verifier, Pkce.generate().verifier)
    }

    @Test fun start_url_encoding() {
        assertEquals(
            "$base/sso/native/start/?code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256&login_hint=a%2Bb%40x.io",
            auth.ssoStartUrl("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", loginHint = "a+b@x.io"),
        )
        assertEquals("$base/sso/native/start/?code_challenge=c&code_challenge_method=S256", auth.ssoStartUrl("c"))
    }

    @Test fun exchange_sends_body_and_returns_token() = runBlocking {
        reply("""{"token":"tok-123"}""")
        assertEquals("tok-123", auth.exchangeSsoCode("c0de", "v3r", "dev-1"))
        val req = server.takeRequest()
        assertEquals("POST", req.method)
        assertEquals("/api/auth/sso/exchange", req.path)
        assertNull(req.getHeader("Authorization"))
        assertEquals(
            JsonObject(mapOf("code" to JsonPrimitive("c0de"), "code_verifier" to JsonPrimitive("v3r"), "device_id" to JsonPrimitive("dev-1"))),
            Json.parseToJsonElement(req.body.readUtf8()),
        )
    }

    @Test fun exchange_400_surfaces_server_message_as_auth() = runBlocking {
        reply("""{"error":"Microsoft sign-in expired. Try again."}""", 400)
        try {
            auth.exchangeSsoCode("used", "v")
            fail("expected AuthException")
        } catch (e: AuthException) {
            assertEquals(400, e.status)
            assertTrue(e.message!!, e.message!!.contains("Microsoft sign-in expired. Try again."))
        }
    }

    @Test fun sso_check_true_and_encodes_email() = runBlocking {
        reply("""{"sso":true}""")
        assertTrue(auth.ssoCheck("a+b@x.io"))
        assertEquals("/sso/check/?email=a%2Bb%40x.io", server.takeRequest().path)
    }

    @Test fun sso_check_false_on_error() = runBlocking {
        reply("oops", 500)
        assertFalse(auth.ssoCheck("a@x.io"))
        server.shutdown() // connection refused
        assertFalse(auth.ssoCheck("a@x.io"))
    }
}
