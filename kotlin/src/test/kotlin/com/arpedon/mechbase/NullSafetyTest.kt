package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/**
 * Hardening tests for issue #2: the SDK must survive a server response that
 * contains an explicit JSON `null` on a property our models declare
 * non-nullable, instead of throwing at decode and taking down the calling
 * screen.
 *
 * Two remediations land together:
 *   A) `coerceInputValues = true` on `SDK_JSON` — for *defaulted* fields,
 *      a present-but-null falls back to the Kotlin default instead of
 *      throwing.
 *   B) Widen *no-default* fields to nullable — for fields like
 *      `Measurement.point_sequence` (genuinely DB-nullable on the server)
 *      and the optional metadata on `MeasurementPoint`.
 *
 * Each test pairs a server response containing an explicit `null` with the
 * expected decoded value (either the default or `null`).
 */
class NullSafetyTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    /**
     * A: defaulted String field with explicit `null` falls back to the default
     * — was the exact production crash on installations 2012/2013 (issue #164
     * server side; #2 client side).
     */
    @Test fun routeDescriptionNullFallsBackToDefault() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
                """{"items":[{"uuid":"r-1","name":"Daily","description":null}],"total":1,"limit":50,"offset":0}""".trimIndent(),
            ),
        )
        val r = client.forInstallation(2012).routes.list()
        assertEquals(1, r.size)
        assertEquals("", r[0].description)
    }

    /** A: defaulted `notes` field on `ItemResponse` survives `null`. */
    @Test fun itemResponseNotesNullFallsBackToDefault() = runBlocking {
        // First call: routes.start() → RouteExecution (status: String)
        server.enqueue(
            MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
                """{"uuid":"exec-1","route_uuid":"route-x","status":"in_progress","started_at":"t","completed_at":null,"session_id":"sess-1"}""".trimIndent(),
            ),
        )
        // Second call: respond() → ItemResponse (status: Int)
        server.enqueue(
            MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
                """{"uuid":"resp-1","route_item_uuid":"item-1","data":{},"notes":null,"status":1,"created_at":"t"}""".trimIndent(),
            ),
        )
        val resp = client.forInstallation(2012).routes.start("route-x").respond(
            routeItemUUID = "item-1", data = mapOf("passed" to true),
        )
        assertEquals("", resp.notes)
    }

    /** A: same default-coercion applies to `RouteDetail.description`. */
    @Test fun routeDetailDescriptionNullFallsBackToDefault() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
                """{"uuid":"r-1","name":"Daily","description":null,"section":null,"items":[]}""".trimIndent(),
            ),
        )
        val d = client.forInstallation(2012).routes.detail("r-1")
        assertEquals("", d.description)
        assertNull(d.section)
    }

    /**
     * B: `Measurement.point_sequence` is genuinely DB-nullable on the server
     * — widening it to `Int? = null` is the only fix; `coerceInputValues`
     * can't help a no-default property.
     */
    @Test fun measurementPointSequenceNullDecodes() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
                """
                {
                  "uuid": "m-1",
                  "measurement_point_id": 1,
                  "point_sequence": null,
                  "data": {"rms": 2.3},
                  "status": "good",
                  "notes": "",
                  "created_at": "2026-04-08T10:00:00Z",
                  "file_url": null
                }
                """.trimIndent(),
            ),
        )
        val m = client.forInstallation(2012).measurements.create(pointId = 1, data = mapOf("rms" to 2.3))
        assertNull(m.pointSequence)
        assertEquals("good", m.status)
    }

    /**
     * B: `MeasurementPoint.transducerType/measurementUnitCode/location` are
     * optional metadata — they shouldn't blow up decode when the server
     * (or a legacy import) leaves them null.
     */
    @Test fun measurementPointOptionalMetadataAllNullDecodes() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
                """
                {
                  "uuid": "p-1",
                  "point_id": 1,
                  "name": "Drive End",
                  "asset_id": 100,
                  "transducer_type": null,
                  "measurement_unit_code": null,
                  "location": null,
                  "status": 1,
                  "external_id": "P-1-DE"
                }
                """.trimIndent(),
            ),
        )
        val p = client.forInstallation(2012).measurementPoints.create(
            PointInput(name = "Drive End", externalId = "P-1-DE"),
        )
        assertNotNull(p)
        assertNull(p.transducerType)
        assertNull(p.measurementUnitCode)
        assertNull(p.location)
    }

    /**
     * B (lockstep with web #164): `SectionRef.section_id` is widened to
     * `Int? = null` so a route whose section has no per-installation id
     * (unassigned — `registry.Section.section_id` is null=True by design)
     * doesn't crash decode.
     */
    @Test fun sectionRefSectionIdNullDecodes() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
                """
                {
                  "uuid": "r-1",
                  "name": "Walkthrough",
                  "description": "",
                  "section": {"section_id": null, "name": "Unassigned"},
                  "items": []
                }
                """.trimIndent(),
            ),
        )
        val d = client.forInstallation(2012).routes.detail("r-1")
        assertNotNull(d.section)
        assertNull(d.section!!.sectionId)
        assertEquals("Unassigned", d.section!!.name)
    }

    /**
     * Regression guard: a fully populated response still decodes the same way
     * after the widening. Catches the case where a serialization-level change
     * accidentally drops a non-null value.
     */
    @Test fun fullyPopulatedResponseStillDecodes() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
                """
                {
                  "uuid": "m-1",
                  "measurement_point_id": 1,
                  "point_sequence": 7,
                  "data": {"rms": 2.3},
                  "status": "good",
                  "notes": "manual",
                  "created_at": "2026-04-08T10:00:00Z",
                  "file_url": null
                }
                """.trimIndent(),
            ),
        )
        val m = client.forInstallation(2012).measurements.create(pointId = 1, data = mapOf("rms" to 2.3))
        assertEquals(7, m.pointSequence)
        assertEquals("manual", m.notes)
    }
}
