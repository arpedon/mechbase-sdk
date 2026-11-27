package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Route + item CRUD, reorder, photos, history; run history; surveys; response notes; non-conformities. */
class RouteEditTest : ApiTest() {
    private val detail = """{"uuid":"$u1","name":"Daily","description":"","section":null,"items":[{"uuid":"$u2","check_id":1,""" +
        """"label":"Oil","item_type":"pass_fail","asset_id":null,"zone_id":null,"measurement_point_id":null,"config":{}}]}"""
    private val item = """{"uuid":"$u2","check_id":1,"label":"Oil","item_type":"pass_fail","asset_id":null,"zone_id":null,""" +
        """"measurement_point_id":null,"config":{}}"""
    private val nc = """{"response_uuid":"$u3","execution_uuid":"$u1","route_uuid":"$u2","route_name":"Daily","route_item_uuid":"$u2",""" +
        """"label":"Oil","asset_id":null,"status":3,"notes":"","started_at":null,"created_at":"x","resolved_at":null,""" +
        """"resolved_by":null,"resolution_comment":""}"""

    @Test fun create_route_with_client_uuids() = runBlocking {
        reply(detail, 201)
        val r = inst.routes.create(
            "Daily",
            listOf(RouteItemInput("Oil", uuid = u2), RouteItemInput("Speed", itemType = "measurement", measurementPointId = 9)),
            uuid = u1,
        )
        assertRequest(
            "POST /api/installations/7/routes",
            """{"name":"Daily","items":[{"label":"Oil","uuid":"$u2"},{"label":"Speed","item_type":"measurement",""" +
                """"measurement_point_id":9}],"uuid":"$u1"}""",
        )
        assertEquals(u2, r.items.single().uuid)
        reply(detail) // retry → 200 with the existing route
        assertEquals(u1, inst.routes.create("Daily", listOf(RouteItemInput("Oil", uuid = u2)), uuid = u1).uuid)
        take()
        val e = assertFails<ConflictException>(409) { inst.routes.create("Daily", emptyList(), uuid = u1) }
        assertEquals(409, e.status)
        assertFails<ValidationException>(422) { inst.routes.create("", emptyList()) }
        Unit
    }

    @Test fun update_delete_history() = runBlocking {
        reply("""{"uuid":"$u1","name":"Nightly","description":"d","section":{"section_id":null,"name":"Hall"}}""")
        assertEquals("Hall", inst.routes.update(u1, name = "Nightly").section?.name)
        assertRequest("PATCH /api/installations/7/routes/$u1", """{"name":"Nightly"}""")

        noContent()
        inst.routes.delete(u1)
        assertRequest("DELETE /api/installations/7/routes/$u1")
        assertFails<ConflictException>(409) { inst.routes.delete(u1) }

        reply("""{"items":[{"uuid":"$u2","route_uuid":"$u1","status":"completed","started_at":null,"completed_at":null,""" +
            """"session_id":"$u3","number":3,"executed_by":null,"answered_count":5,"passed_count":4,"non_conformity_count":1,""" +
            """"max_status":null}],"total":1,"limit":20,"offset":0}""")
        val page = inst.routes.executions(u1, limit = 20)
        assertRequest("GET /api/installations/7/routes/$u1/executions?limit=20&offset=0")
        assertEquals(3, page.items.single().number)
        assertNull(page.items.single().maxStatus)
        assertFails<NotFoundException>(404) { inst.routes.executions(u2) }
        Unit
    }

    @Test fun items_crud_reorder_photo_history() = runBlocking {
        reply(item, 201)
        inst.routes.addItem(u1, RouteItemInput("Steps", itemType = "multi_check", subchecks = listOf("a", "b"), zoneId = 3, uuid = u2))
        assertRequest(
            "POST /api/installations/7/routes/$u1/items",
            """{"label":"Steps","item_type":"multi_check","subchecks":["a","b"],"zone_id":3,"uuid":"$u2"}""",
        )
        assertFails<ConflictException>(409) { inst.routes.addItem(u1, RouteItemInput("x")) }

        reply(item)
        inst.routes.updateItem(u1, u2, label = "Oil level", subchecks = emptyList())
        assertRequest("PATCH /api/installations/7/routes/$u1/items/$u2", """{"label":"Oil level","subchecks":[]}""")

        noContent()
        inst.routes.deleteItem(u1, u2)
        assertRequest("DELETE /api/installations/7/routes/$u1/items/$u2")

        reply("""{"items":[{"uuid":"$u2","check_id":2},{"uuid":"$u3","check_id":1}]}""")
        val numbers = inst.routes.reorderItems(
            u1,
            listOf(ReorderEntry(u2, 1, zoneId = 4), ReorderEntry(u3, 0, clearZone = true, clearAsset = true)),
        )
        assertRequest(
            "POST /api/installations/7/routes/$u1/items/reorder",
            """{"items":[{"uuid":"$u2","position":1,"zone_id":4},{"uuid":"$u3","position":0,"zone_id":null,"asset_id":null}]}""",
        )
        assertEquals(listOf(2, 1), numbers.map { it.checkId })

        reply("""{"uuid":"$u3","name":"p.jpg","kind":"attachment","file_url":"https://x/p.jpg","created_at":"x"}""", 201)
        val photo = File.createTempFile("photo", ".jpg").apply { writeBytes(byteArrayOf(1)); deleteOnExit() }
        inst.routes.addItemPhoto(u1, u2, photo, uuid = u3)
        val rec = take()
        assertEquals("POST /api/installations/7/routes/$u1/items/$u2/photos", rec.line())
        val body = rec.body.readUtf8()
        assertTrue(body.contains("name=\"file\"") && body.contains("name=\"uuid\"") && body.contains(u3))
        assertFails<ConflictException>(409) { inst.routes.addItemPhoto(u1, u2, photo, uuid = u1) }

        reply("""{"items":[{"response_uuid":"$u3","execution_uuid":"$u1","execution_status":"completed","executed_by":null,""" +
            """"started_at":null,"created_at":"x","status":1,"data":{"passed":true},"notes":"","measurement_uuid":null,""" +
            """"point_sequence":null}],"total":1,"limit":50,"offset":0}""")
        val h = inst.routes.itemHistory(u1, u2)
        assertRequest("GET /api/installations/7/routes/$u1/items/$u2/history?limit=50&offset=0")
        assertNull(h.items.single().measurementUuid)
    }

    @Test fun survey_and_response_notes() = runBlocking {
        reply("""{"route":{"uuid":"$u1","name":"Survey","description":"","section":null},"execution":{"uuid":"$u2",""" +
            """"route_uuid":"$u1","status":"in_progress","started_at":"x","completed_at":null,"session_id":"$u3"}}""", 201)
        val s = inst.routes.startSurvey(uuid = u2)
        assertRequest("POST /api/installations/7/surveys", """{"uuid":"$u2"}""")
        assertEquals(u2, s.execution.uuid)
        assertNull(s.route.section)
        assertFails<ConflictException>(409) { inst.routes.startSurvey(uuid = u2) }

        reply("""{"uuid":"$u3","route_item_uuid":"$u2","data":{},"notes":"Replace seal","status":3,"created_at":"x"}""")
        inst.routes.updateResponseNotes(u3, "Replace seal")
        assertRequest("PATCH /api/installations/7/responses/$u3", """{"notes":"Replace seal"}""")
        Unit
    }

    @Test fun non_conformities() = runBlocking {
        reply("""{"items":[$nc],"total":1,"limit":50,"offset":0}""")
        val l = inst.nonConformities.list()
        assertRequest("GET /api/installations/7/non-conformities?status=open&limit=50&offset=0")
        assertNull(l.items.single().resolvedBy)

        reply("""{"items":[],"total":0,"limit":10,"offset":10}""")
        inst.nonConformities.list(status = "all", assetId = 4, limit = 10, offset = 10)
        assertRequest("GET /api/installations/7/non-conformities?status=all&asset_id=4&limit=10&offset=10")

        reply(nc.replace("\"resolved_by\":null", "\"resolved_by\":{\"id\":1,\"name\":\"Ann\"}"))
        assertEquals("Ann", inst.nonConformities.resolve(u3, "Fixed").resolvedBy?.name)
        assertRequest("POST /api/installations/7/non-conformities/$u3/resolve", """{"comment":"Fixed"}""")
        assertFails<ConflictException>(409) { inst.nonConformities.resolve(u3) }
        Unit
    }
}
