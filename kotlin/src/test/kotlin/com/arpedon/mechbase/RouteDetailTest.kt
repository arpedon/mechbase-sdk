package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class RouteDetailTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    /** A realistic RouteDetail response: `section` is an object, two items (pass_fail + numerical). */
    @Test fun detailParsesItemsAndSection() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
                """
                {
                  "uuid": "route-1",
                  "name": "Morning Walk",
                  "description": "Daily checks",
                  "section": {"section_id": 3, "name": "Hall A"},
                  "items": [
                    {
                      "uuid": "item-pf",
                      "check_id": 11,
                      "label": "Visual seal check",
                      "item_type": "pass_fail",
                      "asset_id": 100,
                      "zone_id": 10,
                      "zone_name": "Zone 10",
                      "measurement_point_id": null,
                      "config": {"requirePhotoOnFail": true}
                    },
                    {
                      "uuid": "item-num",
                      "check_id": 12,
                      "label": "Bearing temperature",
                      "item_type": "numerical",
                      "asset_id": 100,
                      "zone_id": 10,
                      "zone_name": "Zone 10",
                      "measurement_point_id": 555,
                      "config": {"min": 0.0, "max": 90.0}
                    }
                  ]
                }
                """.trimIndent(),
            ),
        )

        val detail = client.forInstallation(2012).routes.detail("route-1")

        assertEquals("route-1", detail.uuid)
        assertEquals("Morning Walk", detail.name)
        assertEquals("Daily checks", detail.description)
        assertNotNull("section should deserialize as an object", detail.section)
        assertEquals(3, detail.section?.sectionId)
        assertEquals("Hall A", detail.section?.name)

        assertEquals(2, detail.items.size)

        val pf = detail.items[0]
        assertEquals("item-pf", pf.uuid)
        assertEquals("pass_fail", pf.itemType)
        assertEquals("Visual seal check", pf.label)
        assertEquals(11, pf.checkId)
        assertEquals(100, pf.assetId)
        assertEquals("Zone 10", pf.zoneName)
        assertNull("pass_fail item has no measurement point", pf.measurementPointId)
        assertEquals(true, pf.config["requirePhotoOnFail"]?.jsonPrimitive?.content?.toBoolean())

        val num = detail.items[1]
        assertEquals("item-num", num.uuid)
        assertEquals("numerical", num.itemType)
        assertEquals("Bearing temperature", num.label)
        assertEquals(555, num.measurementPointId)
        assertEquals(90.0, num.config["max"]?.jsonPrimitive?.doubleOrNull)

        val rec = server.takeRequest()
        assertEquals("GET", rec.method)
        assertEquals("/api/installations/2012/routes/route-1", rec.path)
    }

    /** `section` may be absent/null for route-level routes — must not blow up. */
    @Test fun detailToleratesNullSection() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
                """{"uuid":"route-2","name":"No Section","description":"","section":null,"items":[]}""".trimIndent(),
            ),
        )
        val detail = client.forInstallation(2012).routes.detail("route-2")
        assertNull(detail.section)
        assertEquals(0, detail.items.size)
    }
}
