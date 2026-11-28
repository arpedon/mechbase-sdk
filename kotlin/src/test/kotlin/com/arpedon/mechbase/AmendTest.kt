package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Run report and amending a completed run (answer, notes, photos, reading). */
class AmendTest : ApiTest() {
    private val exec get() = inst.routes.execution(u1)
    private val response = """{"uuid":"$u3","route_item_uuid":"$u2","data":{"passed":false},"notes":"","status":3,"created_at":"x"}"""
    private fun file(ext: String) = File.createTempFile("amend", ext).apply { writeBytes(byteArrayOf(1, 2)); deleteOnExit() }

    @Test fun report_parses_nested_nulls() = runBlocking {
        reply(
            """{"execution":{"uuid":"$u1","route_uuid":"$u2","status":"completed","started_at":"x","completed_at":"y",""" +
                """"session_id":"$u3","number":1,"executed_by":{"id":1,"name":"Ann"},"answered_count":1,"passed_count":0,""" +
                """"non_conformity_count":1,"max_status":3},"route":{"uuid":"$u2","name":"Daily","description":"","section":null},""" +
                """"can_amend":true,"totals":{"checks":2,"answered":1,"passed":0,"non_conformities":1},"groups":[{"zone_id":null,""" +
                """"label":"Route","entries":[{"check":{"uuid":"$u2","check_id":1,"label":"Oil","item_type":"measurement",""" +
                """"asset_id":null,"asset_name":null,"zone_id":null,"measurement_point_id":9,"config":{}},"response":{"uuid":"$u3",""" +
                """"data":{},"notes":"","status":3,"created_at":"x","resolved_at":null,"resolved_by":null,"resolution_comment":"",""" +
                """"photos":[{"uuid":"$u1","kind":"thermogram","url":"https://x","name":"t.jpg"}],"reading":{"uuid":"$u1",""" +
                """"point_id":9,"point_sequence":null,"status":3,"data":{"rms":5},"notes":"","created_at":"x"}}}]}],""" +
                """"missing":[],"exceptions":[{"response_uuid":"$u3","route_item_uuid":"$u2","name":"Oil","status":3,"resolved":false}]}""",
        )
        val r = exec.report()
        assertRequest("GET /api/installations/7/executions/$u1/report")
        assertTrue(r.canAmend)
        val entry = r.groups.single().entries.single()
        assertNull(entry.check.assetName)
        assertEquals("thermogram", entry.response.photos.single().kind)
        assertNull(entry.response.reading!!.pointSequence)
        assertFalse(r.exceptions.single().resolved)
        assertFails<NotFoundException>(404) { exec.report() }
        Unit
    }

    @Test fun amend_answer_and_notes() = runBlocking {
        reply(response, 201)
        exec.amendAnswer(u2, mapOf("passed" to false), notes = "late", idempotencyKey = "k-1")
        val r = assertRequest("POST /api/installations/7/executions/$u1/amend/$u2/answer", """{"data":{"passed":false},"notes":"late"}""")
        assertEquals("k-1", r.getHeader("X-Idempotency-Key"))

        reply(response, 201)
        exec.amendAnswer(u2, mapOf("value" to 1.5))
        assertNull(assertRequest("POST /api/installations/7/executions/$u1/amend/$u2/answer").getHeader("X-Idempotency-Key"))

        reply(response)
        exec.amendNotes(u2, "edited")
        assertRequest("PATCH /api/installations/7/executions/$u1/amend/$u2/notes", """{"notes":"edited"}""")

        assertFails<AuthException>(403) { exec.amendNotes(u2, "x") }
        assertFails<ValidationException>(422) { exec.amendAnswer(u2, emptyMap()) }
        Unit
    }

    @Test fun amend_photos() = runBlocking {
        reply("""{"uuid":"$u3","name":"p.jpg","kind":"attachment","file_url":"https://x","created_at":"x"}""", 201)
        exec.amendAddPhoto(u2, file(".jpg"), uuid = u3)
        val rec = take()
        assertEquals("POST /api/installations/7/executions/$u1/amend/$u2/photos", rec.line())
        assertTrue(rec.body.readUtf8().contains(u3))

        noContent()
        exec.amendRemovePhoto(u2, u3)
        assertRequest("DELETE /api/installations/7/executions/$u1/amend/$u2/photos/$u3")
        assertFails<ConflictException>(409) { exec.amendAddPhoto(u2, file(".jpg"), uuid = u1) }
        Unit
    }

    @Test fun amend_reading_multipart() = runBlocking {
        reply(response, 201)
        exec.amendReading(u2, value = 2.5, comment = "re-read", images = listOf(file(".jpg"), file(".jpg")), dataFile = file(".dr"), idempotencyKey = "k-2")
        val rec = take()
        assertEquals("POST /api/installations/7/executions/$u1/amend/$u2/reading", rec.line())
        assertEquals("k-2", rec.getHeader("X-Idempotency-Key"))
        assertTrue(rec.getHeader("Content-Type")!!.startsWith("multipart/form-data"))
        val body = rec.body.readUtf8()
        assertTrue(Regex("name=\"value\"\r\n(?:[^\r\n]+\r\n)*\r\n2\\.5\r\n").containsMatchIn(body))
        assertTrue(body.contains("re-read"))
        assertEquals(2, Regex("name=\"images\"").findAll(body).count())
        assertTrue(body.contains("name=\"data_file\""))

        reply(response, 201)
        exec.amendReading(u2)
        val bare = take().body.readUtf8()
        assertFalse(bare.contains("name=\"value\""))
        assertTrue(bare.contains("name=\"comment\""))

        assertFails<ConflictException>(409) { exec.amendReading(u2, value = 1.0, idempotencyKey = "used") }
        Unit
    }
}
