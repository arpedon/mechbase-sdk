package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

/** Finding create + choices; bearings CRUD and search. */
class FindingsBearingsTest : ApiTest() {
    private val finding = """{"uuid":"$u1","status":"open","fault_type":"bearing","severity":"minor","recommended_action":"",""" +
        """"comment":"","evidence":{},"work_order_ref":"","created_at":"x","updated_at":"x","asset_name":"Pump",""" +
        """"point_name":"DE","point_location":"DE","web_url":"https://x"}"""
    private val bearing = """{"uuid":"$u2","designation":"6205","manufacturer":"SKF","source":"installation","editable":true,""" +
        """"rolling_elements":null,"bpfo":3.58,"bpfi":5.42,"bsf":2.36,"ftf":0.4,"ball_diameter":null,"pitch_diameter":null,""" +
        """"contact_angle":null,"point_count":2,"match":null}"""

    @Test fun create_finding_merges_cursor() = runBlocking {
        reply(finding, 201)
        inst.findings.create(
            9, 12, "bearing", "minor", dueBy = "2026-12-01", comment = "BPFO",
            cursor = FindingCursor(hz = 87.2, amplitude = 0.4, unit = "g", signal = "envelope", df = 0.5),
        )
        assertRequest(
            "POST /api/installations/7/findings/",
            """{"point_id":9,"point_sequence":12,"fault_type":"bearing","severity":"minor","due_by":"2026-12-01",""" +
                """"comment":"BPFO","hz":87.2,"amplitude":0.4,"unit":"g","signal":"envelope","df":0.5}""",
        )
        reply(finding, 201)
        inst.findings.create(9, 12, "bearing", "minor")
        assertRequest("POST /api/installations/7/findings/", """{"point_id":9,"point_sequence":12,"fault_type":"bearing","severity":"minor"}""")

        assertFails<NotFoundException>(404) { inst.findings.create(99, 1, "x", "y") }
        assertFails<ValidationException>(422) { inst.findings.create(9, 99, "x", "y") }
        Unit
    }

    @Test fun choices_query() = runBlocking {
        reply("""{"fault_types":[{"value":"bearing","label":"Bearing"}],"severities":[{"value":"minor","label":"Minor"}],""" +
            """"suggested_fault_type":null,"evidence":{}}""")
        val c = inst.findings.choices()
        assertRequest("GET /api/installations/7/findings/choices/")
        assertNull(c.suggestedFaultType)
        assertEquals("Bearing", c.faultTypes.single().label)

        reply("""{"fault_types":[],"severities":[],"suggested_fault_type":"bearing","evidence":{"hz":87.2}}""")
        assertEquals("bearing", inst.findings.choices(9, 12, FindingCursor(hz = 87.2, signal = "envelope", shaftHz = 24.5)).suggestedFaultType)
        assertRequest("GET /api/installations/7/findings/choices/?point_id=9&point_sequence=12&hz=87.2&signal=envelope&shaft_hz=24.5")
        Unit
    }

    @Test fun bearings_crud_and_search() = runBlocking {
        reply("""{"own":[$bearing],"results":[],"library_count":12000}""")
        val l = inst.bearings.list(q = "6205")
        assertRequest("GET /api/installations/7/bearings?q=6205")
        assertNull(l.own.single().rollingElements)
        assertEquals(2, l.own.single().pointCount)

        reply("""{"own":[],"results":[],"library_count":0}""")
        inst.bearings.list(order = 3.58, sideband = "ftf")
        assertRequest("GET /api/installations/7/bearings?order=3.58&sideband=ftf")

        reply(bearing)
        inst.bearings.get(u2)
        assertRequest("GET /api/installations/7/bearings/$u2")

        reply(bearing, 201)
        inst.bearings.create(BearingInput(designation = "6205", rollingElements = 9, ballDiameter = 7.94, pitchDiameter = 38.5))
        assertRequest("POST /api/installations/7/bearings", """{"designation":"6205","rolling_elements":9,"ball_diameter":7.94,"pitch_diameter":38.5}""")

        reply(bearing)
        inst.bearings.update(u2, BearingInput(manufacturer = "FAG"))
        assertRequest("PATCH /api/installations/7/bearings/$u2", """{"manufacturer":"FAG"}""")

        noContent()
        inst.bearings.delete(u2)
        assertRequest("DELETE /api/installations/7/bearings/$u2")

        assertFails<NotFoundException>(404) { inst.bearings.update(u3, BearingInput(designation = "x")) }
        assertFails<ValidationException>(422) { inst.bearings.create(BearingInput(designation = "x", bpfo = 1.0)) }
        assertThrows(ValidationException::class.java) { runBlocking { inst.bearings.delete("..") } }
        Unit
    }
}
