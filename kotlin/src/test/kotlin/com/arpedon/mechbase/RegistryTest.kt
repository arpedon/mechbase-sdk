package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class RegistryTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    @Test fun createAsset() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"a-1","asset_id":7,"name":"Pump 7","section_id":3,"zone_id":2,
                "machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}""".trimIndent()))
        val a = client.forInstallation(2012).assets.create(AssetInput(name = "Pump 7", externalId = "P-7"))
        assertEquals(7, a.assetId)
        assertEquals("pump", a.equipmentType)
        val rec = server.takeRequest()
        assertEquals("POST", rec.method)
        assertEquals("/api/installations/2012/assets", rec.path)
    }

    @Test fun conflictRaises() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(409).setHeader("Content-Type", "application/json").setBody("""{"detail":"dup"}"""))
        try {
            client.forInstallation(2012).assets.create(AssetInput(externalId = "P-7"))
            org.junit.Assert.fail("expected ConflictException")
        } catch (e: ConflictException) {
            assertEquals(409, e.status)
        }
        Unit
    }

    @Test fun createBatch() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"created":1,"duplicates":0,"errors":0,"results":[
                {"index":0,"status":"created","measurement_point_id":1,"point_sequence":5,
                 "uuid":"m-1","external_id":"E-0","detail":null}]}""".trimIndent()))
        val res = client.forInstallation(2012).measurements.createBatch(listOf(
            MeasurementInput(measurementPointId = 1, data = mapOf("rms" to 2.3), externalId = "E-0")))
        assertEquals(1, res.created)
        assertEquals("created", res.results[0].status)
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/measurements/batch/", rec.path)
    }

    @Test fun iterForPoint() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"items":[{"uuid":"m-1","measurement_point_id":42,"point_sequence":1,
                "data":{},"status":"good","notes":"","created_at":"t1"}],"next_cursor":"CUR2"}""".trimIndent()))
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"items":[{"uuid":"m-2","measurement_point_id":42,"point_sequence":2,
                "data":{},"status":"good","notes":"","created_at":"t2"}],"next_cursor":null}""".trimIndent()))
        val got = mutableListOf<String>()
        client.forInstallation(2012).measurements.iterForPoint(42, pageSize = 1)
            .collect { got.add(it.uuid) }
        assertEquals(listOf("m-1", "m-2"), got)
        // Verify CORRECTION 1: first request sends cursor= (empty), second sends cursor=CUR2
        val req1 = server.takeRequest()
        assertTrue("first request path should contain cursor=: ${req1.path}", req1.path!!.contains("cursor="))
        val req2 = server.takeRequest()
        assertTrue("second request path should contain cursor=CUR2: ${req2.path}", req2.path!!.contains("cursor=CUR2"))
    }
}
