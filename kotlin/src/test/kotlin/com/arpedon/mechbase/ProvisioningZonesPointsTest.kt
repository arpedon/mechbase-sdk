package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** MaintNode commissioning (lookup, claim, credentials, channels, groups), zone files, new point fields. */
class ProvisioningZonesPointsTest : ApiTest() {
    private val balena = "0123456789abcdef0123456789abcdef"
    private val device = """{"node_uuid":"$u1","name":"Node","is_online":false,"last_seen_at":null,"claimed_at":"x","health":{},""" +
        """"health_warnings":[],"health_url":null,"groups":[],"tunnels":[],"token_push":{"state":"queued","queued_at":"x",""" +
        """"pushed_at":null,"failed_at":null},"config":{"applied_version":null,"current_version":"ab","is_current":null},"hardware":null}"""

    @Test fun lookup_claim_credentials() = runBlocking {
        reply("""{"state":"claim","node_uuid":"$u1","name":null,"installation_id":null,"installation_name":null,"is_online":null}""")
        val l = inst.devices.lookup(balena)
        assertRequest("GET /api/installations/7/devices/lookup/$balena")
        assertEquals("claim", l.state)
        assertNull(l.isOnline)
        assertThrows(ValidationException::class.java) { runBlocking { inst.devices.lookup("../x") } }
        assertFails<AuthException>(403) { inst.devices.lookup(balena) }

        reply(device, 201)
        val d = inst.devices.claim(balena, name = "Boiler")
        assertRequest("POST /api/installations/7/devices", """{"balena_uuid":"$balena","name":"Boiler"}""")
        assertEquals("queued", d.tokenPush?.state)
        assertNull(d.config!!.isCurrent)
        assertNull(d.hardware)
        reply(device) // already ours: 200
        inst.devices.claim(balena)
        assertRequest("POST /api/installations/7/devices", """{"balena_uuid":"$balena"}""")
        assertFails<ConflictException>(409) { inst.devices.claim(balena) }
        assertThrows(ValidationException::class.java) { runBlocking { inst.devices.claim("../x") } }

        reply(device.replace("\"queued\"", "\"pushed\""), 202)
        assertEquals("pushed", inst.devices.resendCredentials(u1).tokenPush?.state)
        assertRequest("POST /api/installations/7/devices/$u1/credentials")
        assertFails<NotFoundException>(404) { inst.devices.resendCredentials(u2) }

        // Older server: no token_push/config/hardware.
        val old = SDK_JSON.decodeFromString(Device.serializer(), """{"node_uuid":"$u1"}""")
        assertNull(old.tokenPush); assertNull(old.config)
    }

    @Test fun channels_and_group_create() = runBlocking {
        reply("""[{"uuid":"$u2","name":"hat","hardware_type":"hat","slots":16,"channels":[{"channel":0,"used":true,""" +
            """"mapping_uuid":"$u3","is_active":true,"point_id":9,"point_name":"DE","asset_id":4,"asset_name":"Pump",""" +
            """"sensor":"accelerometer","state":"ok"},{"channel":1,"used":false,"mapping_uuid":null,"is_active":null,""" +
            """"point_id":null,"point_name":null,"asset_id":null,"asset_name":null,"sensor":null,"state":null}]},""" +
            """{"uuid":"$u3","name":"mb","hardware_type":"modbus","slots":null,"channels":[]}]""")
        val groups = inst.devices.channels(u1)
        assertRequest("GET /api/installations/7/devices/$u1/channels")
        assertEquals(16, groups[0].slots)
        assertNull(groups[0].channels[1].state)
        assertNull(groups[1].slots)

        reply(device, 201)
        inst.devices.createGroup(u1, buildJsonObject { put("group_name", "usb"); put("hardware_type", "ul"); put("interval", 600) })
        assertRequest("POST /api/installations/7/devices/$u1/groups", """{"group_name":"usb","hardware_type":"ul","interval":600}""")
        assertFails<ValidationException>(422) { inst.devices.createGroup(u1, buildJsonObject { }) }
        Unit
    }

    @Test fun zone_documents_and_photos() = runBlocking {
        val f = File.createTempFile("zone", ".pdf").apply { writeBytes(byteArrayOf(1)); deleteOnExit() }
        reply("""[{"uuid":"$u1","name":"a.pdf","kind":"manual","url":"https://x","created_at":"x","inherited":true}]""")
        assertTrue(inst.zones.documents(3).single().inherited)
        assertRequest("GET /api/installations/7/zones/3/documents")

        reply("""{"uuid":"$u2","name":"a.pdf","kind":"drawing","url":"https://x","created_at":"x","inherited":false}""", 201)
        inst.zones.addDocument(3, f, kind = "drawing", uuid = u2)
        val rec = take()
        assertEquals("POST /api/installations/7/zones/3/documents", rec.line())
        val body = rec.body.readUtf8()
        assertTrue(body.contains("drawing") && body.contains(u2) && body.contains("name=\"file\""))

        noContent()
        inst.zones.deleteDocument(3, u2)
        assertRequest("DELETE /api/installations/7/zones/3/documents/$u2")
        assertFails<NotFoundException>(404) { inst.zones.deleteDocument(3, u2) }

        reply("""[{"uuid":"$u1","name":"p.jpg","url":"https://x","taken_at":null,"created_at":"x"}]""")
        assertNull(inst.zones.photos(3).single().takenAt)
        assertRequest("GET /api/installations/7/zones/3/photos")

        reply("""{"uuid":"$u3","name":"p.jpg","url":"https://x","taken_at":"x","created_at":"x"}""") // same file again: 200
        assertEquals(u3, inst.zones.addPhoto(3, f, uuid = u3).uuid)
        assertEquals("POST /api/installations/7/zones/3/photos", take().line())
        assertFails<PayloadTooLargeException>(413) { inst.zones.addPhoto(3, f) }

        noContent()
        inst.zones.deletePhoto(3, u3)
        assertRequest("DELETE /api/installations/7/zones/3/photos/$u3")
        Unit
    }

    @Test fun point_analysis_fields_and_clears() = runBlocking {
        val point = """{"uuid":"$u1","point_id":9,"name":"DE","asset_id":4,"transducer_type":"VB","measurement_unit_code":"",""" +
            """"location":"DE","status":1,"nominal_rpm":1480,"bearing":"$u2","speed_ratio":1.0,"envelope_band_low":null,""" +
            """"envelope_band_high":null,"has_own_instructions":true}"""
        reply(point)
        val p = inst.measurementPoints.get(9)
        take()
        assertEquals(1480, p.nominalRpm)
        assertEquals(u2, p.bearing)
        assertNull(p.envelopeBandLow)
        assertTrue(p.hasOwnInstructions)

        reply(point)
        inst.measurementPoints.update(9, PointInput(nominalRpm = 1480, bearing = u2, speedRatio = 0.5, envelopeBandLow = 500, envelopeBandHigh = 10000, instructions = "<p>x</p>"))
        assertRequest(
            "PATCH /api/installations/7/measurement-points/9",
            """{"nominal_rpm":1480,"bearing":"$u2","speed_ratio":0.5,"envelope_band_low":500,"envelope_band_high":10000,"instructions":"<p>x</p>"}""",
        )

        reply(point)
        inst.measurementPoints.update(9, PointInput(clearBearing = true, clearNominalRpm = true, clearEnvelopeBand = true))
        assertRequest(
            "PATCH /api/installations/7/measurement-points/9",
            """{"nominal_rpm":null,"bearing":null,"envelope_band_low":null,"envelope_band_high":null}""",
        )
        reply(point)
        inst.measurementPoints.update(9, PointInput(clearSpeedRatio = true))
        assertRequest("PATCH /api/installations/7/measurement-points/9", """{"speed_ratio":null}""")
        assertThrows(IllegalArgumentException::class.java) {
            runBlocking { inst.measurementPoints.update(9, PointInput(envelopeBandLow = 500, clearEnvelopeBand = true)) }
        }
        assertFails<ValidationException>(422) { inst.measurementPoints.update(9, PointInput(speedRatio = 0.0)) }
        Unit
    }
}
