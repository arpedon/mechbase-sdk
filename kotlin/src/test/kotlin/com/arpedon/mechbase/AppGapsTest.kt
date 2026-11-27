package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Reading get/delete, error detail, finding → reading, retry-safe comments, asset activity, inherited docs, production state. */
class AppGapsTest : ApiTest() {
    private val reading = """{"uuid":"$u1","measurement_point_id":2,"point_sequence":766,"data":{},"status":"good",""" +
        """"notes":"","created_at":"2026-11-27T10:00:00Z"}"""

    @Test fun reading_get_and_delete() = runBlocking {
        reply(reading)
        assertEquals(766, inst.measurements.get(2, 766).pointSequence)
        assertRequest("GET /api/installations/7/measurement-points/2/measurements/766/")
        reply("""{"deleted":true,"uuid":"$u1"}""")
        assertTrue(inst.measurements.delete(2, 766).deleted)
        assertRequest("DELETE /api/installations/7/measurement-points/2/measurements/766/")
        assertFails<NotFoundException>(404) { inst.measurements.get(2, 1) }
        Unit
    }

    @Test fun error_detail_drops_the_status() {
        val e = assertFails<ValidationException>(422) { client.webSession("//x") }
        assertEquals("422 nope", e.message)
        assertEquals("nope", e.detail)
        assertEquals("invalid uuid: x", ValidationException("invalid uuid: x").detail)
    }

    @Test fun finding_links_to_its_reading() = runBlocking {
        reply("""{"uuid":"$u1","status":"open","created_at":"t","updated_at":"t","point_sequence":766}""")
        assertEquals(766, inst.findings.get(u1).pointSequence)
        take()
        reply("""{"uuid":"$u1","status":"open","created_at":"t","updated_at":"t"}""")
        assertNull(inst.findings.get(u1).pointSequence)
    }

    @Test fun comment_create_sends_client_uuid_only_when_given() = runBlocking {
        reply("""{"id":5,"uuid":"$u1","created_at":"t"}""", 201)
        assertEquals(u1, inst.comments.create(1, "b", uuid = u1).uuid)
        assertRequest("POST /api/installations/7/assets/1/comments", """{"body":"b","references":[],"uuid":"$u1"}""")
        reply("""{"id":6,"created_at":"t"}""", 201)
        assertNull(inst.comments.create(1, "b").uuid)
        assertRequest("POST /api/installations/7/assets/1/comments", """{"body":"b","references":[]}""")
        val e = assertFails<ConflictException>(409) { inst.comments.create(1, "b", uuid = u2) }
        assertEquals("nope", e.detail)
    }

    @Test fun activity_by_asset() = runBlocking {
        reply("""{"items":[],"next_cursor":null}""")
        inst.activity(assetId = 4)
        assertRequest("GET /api/installations/7/activity?asset_id=4")
        Unit
    }

    @Test fun documents_inherited_and_asset_production_state() = runBlocking {
        reply("""[{"uuid":"$u1","inherited":true},{"uuid":"$u2"}]""")
        assertEquals(listOf(true, false), inst.documents.list(1).map { it.inherited })
        take()
        reply("""{"uuid":"$u1","asset_id":1,"name":"P","status":1,"running":"on","running_since":"2026-11-27T10:00:00Z"}""")
        val a = inst.assets.get(1)
        assertEquals("on", a.running)
        assertEquals("2026-11-27T10:00:00Z", a.runningSince)
        take()
        reply("""{"uuid":"$u1","asset_id":1,"name":"P","status":1}""")
        assertFalse(inst.assets.get(1).running != null)
    }
}
