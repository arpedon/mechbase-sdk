package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

/** Dashboards: conditional GET (ETag / If-None-Match / 304) and staff editing. */
class DashboardsTest : ApiTest() {
    private val board = """{"uuid":null,"name":"Automatic","is_default":true,"is_automatic":true,"refresh_seconds":60,""" +
        """"readiness":true,"sections":[{"uuid":null,"title":"Pump","meta":"2 points","latest":null,"status":1,""" +
        """"status_label":"Normal","health":100,"readiness":"ok","tiles":[{"uuid":null,"label":"DE","custom_label":"",""" +
        """"point_id":9,"point_uuid":"$u1","asset_id":4,"asset_name":"Pump","transducer_type":"VB","value":null,"unit":null,""" +
        """"decimals":2,"measured_at":null,"lags":false,"status":1,"status_label":"Normal","alarm":false,"stale_since":null,""" +
        """"state":"on","state_since":null,"limits":{"minor":2.8,"major":null},"trend":{"start":"2026-11-27T00:00:00+02:00",""" +
        """"end":"2026-11-28T00:00:00+02:00","low":0.1,"high":2.0,"points":[{"t":"2026-11-27T01:00:00+02:00","v":1.5}]},""" +
        """"timeline":[{"start":"2026-11-27T00:00:00+02:00","end":null,"is_on":true,"status":1,"is_open":true}]}]}]}"""

    @Test fun default_board_fresh_then_not_modified() = runBlocking {
        server.enqueue(json(board).setHeader("ETag", "W/\"abc\""))
        val first = inst.dashboards.default()
        val r1 = take()
        assertEquals("GET /api/installations/7/dashboards/default", r1.line())
        assertNull(r1.getHeader("If-None-Match"))
        first as Conditional.Fresh
        assertEquals("W/\"abc\"", first.etag)
        val tile = first.value.sections.single().tiles.single()
        assertNull(tile.value)
        assertNull(tile.limits?.major)
        assertNull(tile.timeline!!.single().end)
        assertEquals(1.5, tile.trend!!.points.single().v, 0.0)

        server.enqueue(MockResponse().setResponseCode(304))
        assertSame(Conditional.NotModified, inst.dashboards.default(ifNoneMatch = first.etag))
        assertEquals("W/\"abc\"", take().getHeader("If-None-Match"))
    }

    @Test fun get_board_by_uuid_and_errors() = runBlocking {
        server.enqueue(json(board.replace("\"uuid\":null,\"name\":\"Automatic\"", "\"uuid\":\"$u1\",\"name\":\"Mine\"")))
        val r = inst.dashboards.get(u1, ifNoneMatch = "\"x\"")
        val rec = take()
        assertEquals("GET /api/installations/7/dashboards/$u1", rec.line())
        assertEquals("\"x\"", rec.getHeader("If-None-Match"))
        assertEquals("Mine", (r as Conditional.Fresh).value.name)
        assertNull(r.etag)

        assertFails<NotFoundException>(404) { inst.dashboards.get(u2) }
        assertFails<AuthException>(403) { inst.dashboards.default() }
        assertThrows(ValidationException::class.java) { runBlocking { inst.dashboards.get("../x") } }
        Unit
    }

    @Test fun list_create_update_delete_save_automatic() = runBlocking {
        val summary = """{"uuid":"$u1","name":"Mine","is_default":false,"is_automatic":false}"""
        reply("""[{"uuid":null,"name":"Automatic","is_default":true,"is_automatic":true}]""")
        assertNull(inst.dashboards.list().single().uuid)
        assertRequest("GET /api/installations/7/dashboards")

        reply(summary, 201)
        inst.dashboards.create()
        assertRequest("POST /api/installations/7/dashboards", """{"name":""}""")

        reply(summary)
        inst.dashboards.update(u1, isDefault = true)
        assertRequest("PATCH /api/installations/7/dashboards/$u1", """{"is_default":true}""")

        noContent()
        inst.dashboards.delete(u1)
        assertRequest("DELETE /api/installations/7/dashboards/$u1")

        reply(summary, 201)
        inst.dashboards.saveAutomatic()
        assertRequest("POST /api/installations/7/dashboards/save-automatic")
        assertFails<ValidationException>(422) { inst.dashboards.saveAutomatic() }
        assertFails<AuthException>(403) { inst.dashboards.create("x") }
        Unit
    }

    @Test fun sections_tiles_reorder() = runBlocking {
        noContent()
        inst.dashboards.reorder(u1, listOf(LayoutSection(u2, listOf(u3)), LayoutSection(u3)))
        assertRequest("POST /api/installations/7/dashboards/$u1/reorder", """{"sections":[{"id":"$u2","tiles":["$u3"]},{"id":"$u3"}]}""")

        reply("""{"uuid":"$u2","title":"New section","position":1}""", 201)
        assertEquals(1, inst.dashboards.addSection(u1).position)
        assertRequest("POST /api/installations/7/dashboards/$u1/sections", """{"title":""}""")

        reply("""{"uuid":"$u2","title":"Hall","position":1}""")
        inst.dashboards.renameSection(u1, u2, "Hall")
        assertRequest("PATCH /api/installations/7/dashboards/$u1/sections/$u2", """{"title":"Hall"}""")

        noContent()
        inst.dashboards.deleteSection(u1, u2)
        assertRequest("DELETE /api/installations/7/dashboards/$u1/sections/$u2")

        reply("""[{"uuid":"$u3","section":"$u2","point_id":null,"label":"DE","custom_label":"","position":0}]""", 201)
        assertNull(inst.dashboards.addTiles(u1, u2, listOf(9, 10)).single().pointId)
        assertRequest("POST /api/installations/7/dashboards/$u1/tiles", """{"section":"$u2","point_ids":[9,10]}""")

        reply("""{"uuid":"$u3","section":"$u2","point_id":9,"label":"Motor","custom_label":"Motor","position":0}""")
        inst.dashboards.renameTile(u1, u3, "Motor")
        assertRequest("PATCH /api/installations/7/dashboards/$u1/tiles/$u3", """{"label":"Motor"}""")

        noContent()
        inst.dashboards.removeTile(u1, u3)
        assertRequest("DELETE /api/installations/7/dashboards/$u1/tiles/$u3")

        val e = assertFails<ValidationException>(422) { inst.dashboards.reorder(u1, emptyList()) }
        assertTrue(e.message!!.contains("nope"))
    }
}
