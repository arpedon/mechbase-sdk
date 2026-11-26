package com.arpedon.mechbase

import java.io.File
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Comments, documents and alarm rules: method, path, body, decode. */
class CommentsDocumentsAlarmsTest {
    private lateinit var server: MockWebServer
    private lateinit var inst: Installation

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        inst = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/')).forInstallation(7)
    }
    @After fun tearDown() { server.shutdown() }

    private fun json(body: String, code: Int = 200) =
        MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    private val comment = """{"id":9,"body":"<p>x</p>","body_text":"x","author_name":"A","created_at":"2026-01-01T00:00:00Z",""" +
        """"edited_at":null,"references":[{"point_id":5,"point_sequence":null}],"is_finding":false,"editable":true}"""
    private val rule = """{"uuid":"6f1c0000-0000-4000-8000-000000000001","scope":"point","method":"threshold","data_key":"",""" +
        """"effective_data_key":"velocity","direction":"high","minor_threshold":2.5,"major_threshold":null,""" +
        """"threshold_mode":"absolute","source":null}"""
    private val ruleId = "6f1c0000-0000-4000-8000-000000000001"

    @Test fun comments_list() = runBlocking {
        server.enqueue(json("""{"items":[$comment],"total":21,"limit":10,"offset":20}"""))
        val page = inst.comments.list(3, limit = 10, offset = 20)
        val r = server.takeRequest()
        assertEquals("GET /api/installations/7/assets/3/comments?limit=10&offset=20", "${r.method} ${r.path}")
        assertEquals(21, page.total)
        assertNull(page.items.single().editedAt)
        assertEquals(5, page.items.single().references.single().pointId)
        assertNull(page.items.single().references.single().pointSequence)
    }

    @Test fun comments_create() = runBlocking {
        server.enqueue(json(comment, 201))
        val c = inst.comments.create(3, "hi", listOf(CommentReferenceIn(5, 2)))
        val r = server.takeRequest()
        assertEquals("POST /api/installations/7/assets/3/comments", "${r.method} ${r.path}")
        assertEquals("""{"body":"hi","references":[{"point_id":5,"point_sequence":2}]}""", r.body.readUtf8())
        assertTrue(c.editable)
    }

    @Test fun comments_update_sends_empty_reference_set() = runBlocking {
        server.enqueue(json(comment))
        inst.comments.update(3, 9, "yo")
        val r = server.takeRequest()
        assertEquals("PATCH /api/installations/7/assets/3/comments/9", "${r.method} ${r.path}")
        assertEquals("""{"body":"yo","references":[]}""", r.body.readUtf8())
    }

    @Test fun comments_delete() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(204))
        inst.comments.delete(3, 9)
        val r = server.takeRequest()
        assertEquals("DELETE /api/installations/7/assets/3/comments/9", "${r.method} ${r.path}")
    }

    @Test fun documents_list() = runBlocking {
        server.enqueue(json("""[{"uuid":"d1","name":"a.pdf","kind":"manual","url":"/d","created_at":"2026-01-01T00:00:00Z"}]"""))
        val l = inst.documents.list(3)
        val r = server.takeRequest()
        assertEquals("GET /api/installations/7/assets/3/documents", "${r.method} ${r.path}")
        assertEquals("manual", l.single().kind)
    }

    @Test fun documents_add_posts_multipart() = runBlocking {
        server.enqueue(json("""{"uuid":"d1","name":"document.pdf","kind":"manual","url":"/d","created_at":"2026-01-01T00:00:00Z"}""", 201))
        val f = File.createTempFile("doc", ".bin").apply { writeText("PDF"); deleteOnExit() }
        val d = inst.documents.add(3, f, kind = "manual", uuid = "d1")
        val r = server.takeRequest()
        assertEquals("POST /api/installations/7/assets/3/documents", "${r.method} ${r.path}")
        assertTrue(r.getHeader("Content-Type")!!.startsWith("multipart/form-data"))
        val b = r.body.readUtf8()
        assertTrue(b, b.contains("""name="kind"""") && b.contains("manual") && b.contains("""name="uuid"""") && b.contains("d1"))
        assertTrue(b, b.contains("filename=\"${f.name}\"") && b.contains("PDF"))
        assertEquals("d1", d.uuid)
    }

    @Test fun documents_delete() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(204))
        inst.documents.delete(3, ruleId)
        val r = server.takeRequest()
        assertEquals("DELETE /api/installations/7/assets/3/documents/$ruleId", "${r.method} ${r.path}")
    }

    @Test fun alarm_rules_list() = runBlocking {
        server.enqueue(json("[$rule]"))
        val l = inst.alarmRules.list(5)
        val r = server.takeRequest()
        assertEquals("GET /api/installations/7/measurement-points/5/alarm-rules", "${r.method} ${r.path}")
        assertEquals("point", l.single().scope)
        assertEquals(2.5, l.single().minorThreshold!!, 0.0)
        assertNull(l.single().majorThreshold)
        assertNull(l.single().source)
    }

    @Test fun alarm_rules_create() = runBlocking {
        server.enqueue(json(rule, 201))
        inst.alarmRules.create(5, 2.5, 4.0)
        val r = server.takeRequest()
        assertEquals("POST /api/installations/7/measurement-points/5/alarm-rules", "${r.method} ${r.path}")
        assertEquals(
            """{"method":"threshold","data_key":"","direction":"high","minor_threshold":2.5,"major_threshold":4.0}""",
            r.body.readUtf8(),
        )
    }

    @Test fun alarm_rules_update_sends_only_given_fields() = runBlocking {
        server.enqueue(json(rule))
        inst.alarmRules.update(5, ruleId, majorThreshold = 6.0)
        val r = server.takeRequest()
        assertEquals("PATCH /api/installations/7/measurement-points/5/alarm-rules/$ruleId", "${r.method} ${r.path}")
        assertEquals("""{"major_threshold":6.0}""", r.body.readUtf8())
    }

    @Test fun alarm_rules_delete() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(204))
        inst.alarmRules.delete(5, ruleId)
        val r = server.takeRequest()
        assertEquals("DELETE /api/installations/7/measurement-points/5/alarm-rules/$ruleId", "${r.method} ${r.path}")
    }
}
