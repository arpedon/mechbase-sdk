package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/** Findings, analytics exports, token revoke and hotspot edit: method, path, body, decode. */
class FindingsExportsTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    private fun json(body: String, code: Int = 200) =
        MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    private val finding = """{"uuid":"f-1","status":"open","fault_type":"imb","fault_type_display":"Imbalance",""" +
        """"severity":"major","recommended_action":"balance","due_by":"2026-12-01","comment":"","evidence":{"a":1},""" +
        """"work_order_ref":"","acknowledged_at":null,"closed_at":null,"created_at":"2026-11-01T00:00:00Z",""" +
        """"updated_at":"2026-11-01T00:00:00Z","created_by":null,"asset_id":3,"asset_external_id":"A-3",""" +
        """"asset_name":"Pump","point_id":5,"point_external_id":null,"point_name":"DE","point_location":"x",""" +
        """"measurement_uuid":null,"measurement_external_id":null,"measurement_timestamp":null,"web_url":"https://w"}"""

    @Test fun findings_list_sends_filters_and_decodes_page() = runBlocking {
        server.enqueue(json("""{"items":[$finding],"next_cursor":"c2"}"""))
        val page = client.forInstallation(2012).findings.list(cursor = "c1", limit = 10, status = "open", assetId = 3)
        val rec = server.takeRequest()
        assertEquals("GET", rec.method)
        assertEquals("/api/installations/2012/findings/?cursor=c1&limit=10&status=open&asset_id=3", rec.path)
        assertEquals("c2", page.nextCursor)
        assertEquals("A-3", page.items.single().assetExternalId)
        assertEquals("Imbalance", page.items.single().faultTypeDisplay)
    }

    @Test fun findings_get_decodes() = runBlocking {
        server.enqueue(json(finding))
        val f = client.forInstallation(2012).findings.get("f-1")
        assertEquals("/api/installations/2012/findings/f-1/", server.takeRequest().path)
        assertEquals("f-1", f.uuid)
    }

    @Test fun findings_set_status_posts_body() = runBlocking {
        server.enqueue(json(finding.replace("\"open\"", "\"acknowledged\"").replace("\"work_order_ref\":\"\"", "\"work_order_ref\":\"WO-9\"")))
        val f = client.forInstallation(2012).findings.setStatus("f-1", "acknowledged", "WO-9")
        val rec = server.takeRequest()
        assertEquals("POST", rec.method)
        assertEquals("/api/installations/2012/findings/f-1/status/", rec.path)
        assertEquals("""{"status":"acknowledged","work_order_ref":"WO-9"}""", rec.body.readUtf8())
        assertEquals("WO-9", f.workOrderRef)
    }

    @Test fun exports_create_posts_and_decodes_202() = runBlocking {
        server.enqueue(json("""{"job_uuid":"j-1","state":"queued","status_url":"/s"}""", 202))
        val job = client.forInstallation(2012).exports.create("findings", filters = ExportFilters(assetId = 3))
        val rec = server.takeRequest()
        assertEquals("POST", rec.method)
        assertEquals("/api/installations/2012/analytics/exports/", rec.path)
        assertEquals("""{"dataset":"findings","format":"csv","filters":{"asset_id":3}}""", rec.body.readUtf8())
        assertEquals("j-1", job.jobUuid)
    }

    @Test fun exports_status_decodes() = runBlocking {
        server.enqueue(json("""{"job_uuid":"j-1","dataset":"findings","file_format":"csv","state":"done","row_count":4,""" +
            """"byte_size":120,"download_url":"/d?sig=z","expires_at":null,"created_at":"2026-11-01T00:00:00Z"}"""))
        val st = client.forInstallation(2012).exports.status("j-1")
        assertEquals("/api/installations/2012/analytics/exports/j-1/", server.takeRequest().path)
        assertEquals(4, st.rowCount)
        assertEquals("", st.error)
    }

    @Test fun exports_download_returns_raw_bytes_with_sig() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "text/csv").setBody("a,b\n1,2\n"))
        val bytes = client.forInstallation(2012).exports.download("j-1", sig = "z")
        val rec = server.takeRequest()
        assertEquals("GET", rec.method)
        assertEquals("/api/installations/2012/analytics/exports/j-1/download/?sig=z", rec.path)
        assertArrayEquals("a,b\n1,2\n".toByteArray(), bytes)
    }

    @Test fun revoke_token_posts() = runBlocking {
        server.enqueue(json("{}"))
        client.revokeToken()
        val rec = server.takeRequest()
        assertEquals("POST", rec.method)
        assertEquals("/api/auth/token/revoke", rec.path)
        assertEquals("Bearer tok", rec.getHeader("Authorization"))
    }

    @Test fun set_hotspots_patches_full_replacement() = runBlocking {
        server.enqueue(json("""{"uuid":"m-1","measurement_point_id":5,"point_sequence":1,"data":{},"status":"good","notes":"","created_at":"2026-01-01T00:00:00Z"}"""))
        val m = client.forInstallation(2012).measurements.setHotspots(
            "m-1", listOf(HotCluster(10.0, 20.0, 80.5, 12.0, 2, "manual")),
        )
        val rec = server.takeRequest()
        assertEquals("PATCH", rec.method)
        assertEquals("/api/installations/2012/measurements/m-1/hotspots/", rec.path)
        assertEquals(
            """{"hot_clusters":[{"cx_pct":10.0,"cy_pct":20.0,"max_temp_c":80.5,"delta_t_c":12.0,"severity":2,"source":"manual"}]}""",
            rec.body.readUtf8(),
        )
        assertEquals("m-1", m.uuid)
    }
}
