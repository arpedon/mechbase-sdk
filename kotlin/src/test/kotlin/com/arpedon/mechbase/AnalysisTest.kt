package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertThrows
import org.junit.Test

/** Reading analysis, process, compare (ETag), trend, fault record, baselines, notes. */
class AnalysisTest : ApiTest() {
    private val units = """{"acceleration":"g","velocity":"mm/s","temperature":"°C","frequency":"CPM","frequency_scale":60.0}"""

    @Test fun reading_analysis_vibration_with_nulls() = runBlocking {
        reply(
            """{"uuid":"$u1","point_id":9,"point_sequence":12,"created_at":"2026-11-27T10:00:00Z","status":"processed",""" +
                """"notes":"","transducer_type":"VB","source":null,"previous_sequence":11,"next_sequence":null,"data":{"rms":1.2},""" +
                """"display_units":{"rms":{"native":"mm/s","unit":"in/s","scale":0.0393,"offset":0}},"units":$units,""" +
                """"filter":{"highpass_hz":10.0,"lowpass_hz":null},"vibration":{"fs":25600.0,"n_lines":3200,""" +
                """"freq_resolution_hz":2.0,"source_resolution_hz":0.5,"fmax_hz":null,"env_band_hz":null,""" +
                """"waveform":{"accel":{"values":[0.1,-0.1],"t_s":[0.0,0.5],"t0_s":0.0,"dt_s":0.5,"n_source":4096},""" +
                """"velocity":null,"envelope":null},"spectrum":{"freq_hz":[0,2],"accel":[0,1],"velocity":[0,2],"envelope":[],"n_source":8192},""" +
                """"thresholds":{"velocity":{"x":[0,1000],"y":[2.8,2.8]}},"bearing_markers":[{"kind":"bpfo","label":"BPFO","hz":87.2,"harmonic":1}],""" +
                """"order":null},"thermography":null,"attachments":[]}""",
        )
        val a = inst.analysis.reading(9, 12, highpassHz = 10.0)
        assertRequest("GET /api/installations/7/measurement-points/9/measurements/12/analysis?highpass_hz=10.0")
        assertEquals(60.0, a.units.frequencyScale, 0.0)
        val v = a.vibration!!
        assertEquals(listOf(0.0, 0.5), v.waveform!!.accel.t)
        assertNull(v.waveform!!.velocity)
        assertNull(v.order)
        assertEquals(0.5, v.sourceResolutionHz, 0.0)
        assertEquals(2.8, v.thresholds.getValue("velocity").y.first(), 0.0)
        assertNull(a.nextSequence)
        assertNull(a.filter!!.lowpassHz)

        assertFails<ValidationException>(422) { inst.analysis.reading(9, 12, highpassHz = 1e9) }
        assertFails<NotFoundException>(404) { inst.analysis.reading(9, 99) }
        Unit
    }

    @Test fun reading_analysis_thermography() = runBlocking {
        reply(
            """{"uuid":"$u1","point_id":9,"point_sequence":1,"created_at":"x","status":"processed","notes":"","transducer_type":"IR",""" +
                """"data":{},"display_units":{},"units":$units,"thermography":{"thermograms":[{"uuid":"$u2","url":"https://x/t.jpg",""" +
                """"processed":true,"mean_temp":null,"min_temp":null,"max_temp":80.5,"hot_clusters":[{"cx_pct":10,"cy_pct":20,""" +
                """"max_temp":null,"delta_t":12.0,"severity":3,"source":null}]}],"hotspot_count":1,"worst_delta_t":12.0},""" +
                """"attachments":[{"uuid":"$u3","name":"t.jpg","kind":"thermogram","file_url":"https://x/t.jpg","created_at":"x"}]}""",
        )
        val t = inst.analysis.reading(9, 1)
        take()
        assertNull(t.vibration)
        assertEquals(12.0, t.thermography!!.thermograms.single().hotClusters.single().deltaT!!, 0.0)
        assertEquals("thermogram", t.attachments.single().kind)
    }

    @Test fun process_body_and_parse() = runBlocking {
        reply("""{"type":"velocity","units":$units,"cursors":[{"point_sequence":12,"x":[1,2],"y":[3,4],"peaks":[{"x":2,"y":4}]},""" +
            """{"point_sequence":99,"x":[],"y":[]}]}""")
        val p = inst.analysis.process(9, 12, peakCount = 5, cursors = listOf(12, 99), highPass = 2.0)
        assertRequest(
            "POST /api/installations/7/measurement-points/9/measurements/12/process",
            """{"type":"velocity","high_pass":2.0,"low_pass":0.0,"db_scale":false,"peak_count":5,"cursors":[12,99]}""",
        )
        assertEquals(4.0, p.cursors[0].peaks.single().y, 0.0)
        assertEquals(emptyList<Peak>(), p.cursors[1].peaks)
    }

    @Test fun compare_etag_and_304() = runBlocking {
        val body = """{"point_id":9,"spectrum":"envelope","units":$units,"zoom_range_hz":null,"baseline":null,"cursors":[""" +
            """{"index":0,"point_sequence":12,"color":"#f00","created_at":"x","status":"processed","fs":null,"metrics":{"rms":1},""" +
            """"freq_hz":[0,1],"values":[0,2],"markers":[]}]}"""
        server.enqueue(json(body).setHeader("ETag", "\"e1\""))
        val r = inst.analysis.compare(9, listOf(12, 11), spectrum = "envelope") as Conditional.Fresh
        assertRequest("GET /api/installations/7/measurement-points/9/compare?seq=12%2C11&spectrum=envelope")
        assertEquals("\"e1\"", r.etag)
        assertNull(r.value.baseline)
        assertNull(r.value.cursors.single().fs)

        server.enqueue(MockResponse().setResponseCode(304))
        assertSame(Conditional.NotModified, inst.analysis.compare(9, listOf(12, 11), ifNoneMatch = "\"e1\""))
        assertEquals("\"e1\"", take().getHeader("If-None-Match"))

        assertFails<ValidationException>(422) { inst.analysis.compare(9, (1..9).toList()) }
        assertThrows(IllegalArgumentException::class.java) { runBlocking { inst.analysis.compare(9, emptyList()) } }
        assertEquals(0, server.requestCount - 3)
        Unit
    }

    @Test fun trend_and_fault_record() = runBlocking {
        reply("""{"series":[{"point_id":9,"name":"DE","unit":"mm/s","type":"VB","location":"DE","thresholds":null,""" +
            """"measurements":[{"t":"x","v":1.0,"status":1,"off":false}]}],"production_status":[{"t":"x","on":true}],""" +
            """"window":{"start":"a","end":"b"},"empty":false}""")
        val t = inst.analysis.trend(4, type = "VB")
        assertRequest("GET /api/installations/7/assets/4/trend?type=VB")
        assertNull(t.series.single().thresholds)
        assertEquals(true, t.productionStatus.single().on)

        reply("""{"asset_id":4,"at":"2026-11-27T10:00:00Z","window":{"start":"a","end":"b"},"trigger_point_id":null,""" +
            """"rows":[{"point_id":9,"name":"DE","location":"DE","transducer_type":"TM","status":3,"unit":"°C",""" +
            """"series":[{"t":"x","v":71.0}],"thresholds":{"minor":70,"major":null,"direction":"high"}}]}""")
        val f = inst.analysis.faultRecord(4, "2026-11-27T10:00:00Z", pointId = 9)
        assertRequest("GET /api/installations/7/assets/4/fault-record?at=2026-11-27T10%3A00%3A00Z&point=9")
        assertNull(f.triggerPointId)
        assertNull(f.rows.single().thresholds.major)
        assertFails<ValidationException>(422) { inst.analysis.faultRecord(4, "bad") }
        Unit
    }

    @Test fun baselines() = runBlocking {
        reply("""{"detail":"Baseline fit queued."}""", 202)
        assertEquals("Baseline fit queued.", inst.analysis.createBaseline(9, "2026-10-01"))
        assertRequest("POST /api/installations/7/measurement-points/9/baseline", """{"refit_from":"2026-10-01"}""")

        reply("""{"detail":"Cleared."}""")
        inst.analysis.clearBaseline(9)
        assertRequest("DELETE /api/installations/7/measurement-points/9/baseline")

        reply("""{"eligible":42,"fit_min":100}""")
        assertEquals(100, inst.analysis.baselinePreview(9, since = "2026-10-01").fitMin)
        assertRequest("GET /api/installations/7/measurement-points/9/baseline/preview?since=2026-10-01")

        assertFails<ValidationException>(422) { inst.analysis.createBaseline(9, "2026-11-26") }
        Unit
    }

    @Test fun measurement_notes_patch() = runBlocking {
        reply("""{"uuid":"$u1","measurement_point_id":9,"point_sequence":12,"data":{},"status":"processed","notes":"<p>ok</p>","created_at":"x"}""")
        assertEquals("<p>ok</p>", inst.measurements.updateNotes(9, 12, "<p>ok</p>").notes)
        assertRequest("PATCH /api/installations/7/measurement-points/9/measurements/12/", """{"notes":"<p>ok</p>"}""")
        assertFails<AuthException>(403) { inst.measurements.updateNotes(9, 12, "") }
        Unit
    }
}
