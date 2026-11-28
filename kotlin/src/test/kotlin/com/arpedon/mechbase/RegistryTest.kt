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
        assertEquals("POST", rec.method)
        assertTrue(rec.body.readUtf8().contains("\"items\":["))
    }

    @Test fun assetWriteVerbs() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"a-1","asset_id":7,"name":"Pump 7b","section_id":3,"zone_id":2,"machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}""".trimIndent()))
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"a-1","asset_id":7,"name":"Pump 7c","section_id":3,"zone_id":2,"machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}""".trimIndent()))
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody(
            """{"deleted":true,"uuid":"a-1"}""".trimIndent()))

        val assets = client.forInstallation(2012).assets
        val up = assets.upsert(AssetInput(externalId = "P-7", name = "Pump 7b"))
        assertEquals("Pump 7b", up.name)
        val updated = assets.update(7, AssetInput(name = "Pump 7c"))
        assertEquals("Pump 7c", updated.name)
        val del = assets.delete(7, cascade = true)
        assertTrue(del.deleted)

        val r1 = server.takeRequest()
        assertEquals("PUT", r1.method)
        assertEquals("/api/installations/2012/assets", r1.path)

        val r2 = server.takeRequest()
        assertEquals("PATCH", r2.method)
        assertEquals("/api/installations/2012/assets/7", r2.path)
        val patchBody = r2.body.readUtf8()
        assertTrue(patchBody.contains("\"name\":\"Pump 7c\""))
        assertTrue("PATCH body must omit null fields", !patchBody.contains("external_id"))

        val r3 = server.takeRequest()
        assertEquals("DELETE", r3.method)
        assertEquals("/api/installations/2012/assets/7?cascade=true", r3.path)
    }

    @Test fun sectionsAndZones() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"s-1","section_id":3,"name":"Hall A","external_id":"S-1"}""".trimIndent()))
        server.enqueue(MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"z-1","zone_id":9,"name":"Zone 9","section_id":3,"external_id":"Z-9"}""".trimIndent()))

        val inst = client.forInstallation(2012)
        val s = inst.sections.create(SectionInput(name = "Hall A", externalId = "S-1"))
        assertEquals(3, s.sectionId)
        assertEquals("Hall A", s.name)
        val z = inst.zones.create(ZoneInput(name = "Zone 9", externalId = "Z-9", sectionExternalId = "S-1"))
        assertEquals(9, z.zoneId)

        val r1 = server.takeRequest()
        assertEquals("POST", r1.method)
        assertEquals("/api/installations/2012/sections", r1.path)
        val r2 = server.takeRequest()
        assertEquals("POST", r2.method)
        assertEquals("/api/installations/2012/zones", r2.path)
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

    private fun ok(body: String, code: Int = 200) =
        MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    @Test fun assetTypeOmittedNullCode() = runBlocking {
        val assets = client.forInstallation(2012).assets
        val a = """{"uuid":"a","asset_id":1,"name":"P","status":1,"asset_type":"QB-STD","fed_from":7}"""
        repeat(5) { server.enqueue(ok(a)) }
        assertEquals("QB-STD", assets.update(1, AssetInput(name = "P")).assetType)
        assets.update(1, AssetInput(clearAssetType = true))
        assets.update(1, AssetInput(assetType = "QB-STD"))
        assertEquals("""{"name":"P"}""", server.takeRequest().body.readUtf8())
        assertEquals("""{"asset_type":null}""", server.takeRequest().body.readUtf8())
        assertEquals("""{"asset_type":"QB-STD"}""", server.takeRequest().body.readUtf8())
        assertEquals(7, assets.update(1, AssetInput(fedFrom = 7)).fedFrom)
        assets.update(1, AssetInput(clearFedFrom = true))
        assertEquals("""{"fed_from":7}""", server.takeRequest().body.readUtf8())
        assertEquals("""{"fed_from":null}""", server.takeRequest().body.readUtf8())
    }

    @Test fun zoneGuestViewAndEnsureChecklist() = runBlocking {
        server.enqueue(ok("""{"uuid":"z","zone_id":3,"name":"Z","guest_view":true}"""))
        server.enqueue(ok("""{"uuid":"z","name":"Z"}"""))
        server.enqueue(ok("""{"route_uuid":"r","created":true}"""))
        val inst = client.forInstallation(2012)
        assertTrue(inst.zones.update(3, ZoneInput(guestView = true)).guestView)
        val z = server.takeRequest()
        assertEquals("PATCH", z.method)
        assertEquals("""{"guest_view":true}""", z.body.readUtf8())
        assertEquals(false, inst.zones.get(3).guestView)
        server.takeRequest()
        val c = inst.assets.ensureChecklist(1)
        assertEquals("r", c.routeUuid)
        assertTrue(c.created)
        val r = server.takeRequest()
        assertEquals("POST", r.method)
        assertEquals("/api/installations/2012/assets/1/checklist", r.path)
    }

    @Test fun assetTypesPaths() = runBlocking {
        val t = """{"uuid":"t","code":"QB-STD","name":"QB","checklist":[{"label":"x"}],"asset_count":2,"document_count":1}"""
        val d = """{"uuid":"d","name":"m.pdf","kind":"manual","url":"u","created_at":"c"}"""
        server.enqueue(ok("[$t]")); server.enqueue(ok(t)); server.enqueue(ok(t)); server.enqueue(ok(t))
        server.enqueue(ok("""{"deleted":true,"uuid":"t"}""")); server.enqueue(ok("[$d]")); server.enqueue(ok(d, 201))
        server.enqueue(MockResponse().setResponseCode(204))
        val at = client.forInstallation(2012).assetTypes
        val list = at.list()
        assertEquals(1, list[0].documentCount); assertEquals(1, list[0].checklist.size)
        at.get("QB-STD")
        at.upsert(AssetTypeInput(code = "QB-STD", name = "QB"))
        at.update("QB-STD", AssetTypeInput(manufacturer = "ACME"))
        assertTrue(at.delete("QB-STD").deleted)
        assertEquals(1, at.documents("QB-STD").size)
        val f = java.io.File.createTempFile("doc", ".pdf").apply { writeText("%PDF"); deleteOnExit() }
        at.addDocument("QB-STD", f, kind = "manual")
        at.deleteDocument("QB-STD", "11111111-1111-1111-1111-111111111111")
        val base = "/api/installations/2012/asset-types"
        val got = (1..8).map { server.takeRequest().let { r -> "${r.method} ${r.path}" } }
        assertEquals(listOf("GET $base", "GET $base/QB-STD", "PUT $base", "PATCH $base/QB-STD", "DELETE $base/QB-STD",
            "GET $base/QB-STD/documents", "POST $base/QB-STD/documents",
            "DELETE $base/QB-STD/documents/11111111-1111-1111-1111-111111111111"), got)
    }
}
