package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test

/** Devices, sources and staff tunnels: method, path, body, decode. */
class DevicesTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient
    private val inst get() = client.forInstallation(7)

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    private fun json(body: String, code: Int = 200) =
        MockResponse().setResponseCode(code).setHeader("Content-Type", "application/json").setBody(body)

    private val node = "6f1e2d3c-4b5a-4968-8776-5a4b3c2d1e0f"
    private val group = "6f1c0000-0000-4000-8000-000000000001"
    private val src = "6f1c0000-0000-4000-8000-000000000002"
    private val device = """{"node_uuid":"$node","name":"Node A","is_online":true,"last_seen_at":null,"claimed_at":null,""" +
        """"health":{"cpu_usage":95},"health_warnings":["CPU 95%"],"health_url":null,"groups":[{"uuid":"$group",""" +
        """"name":"hat","hardware_type":"hat","hardware_config":{},"interval":600,"sample_rate":null,"samples":null,""" +
        """"channels":[{"uuid":"m1","channel":3,"point_id":1,"point_name":"DE","asset_id":1,"asset_name":"Pump",""" +
        """"sensor":"accelerometer","last_seen_at":null,"stale_since":null,"state":"waiting"}]}],"tunnels":[{"uuid":"t1",""" +
        """"name":"logo","label":"LOGO","kind":"http","staff_only":false,"web_url":"https://x/t1/","local_port":null,"visitor_url":null}]}"""
    private val source = """{"uuid":"$src","source_type":"maintnode","device_id":"$node","device_name":"Node A",""" +
        """"group":{"uuid":"$group","name":"hat","hardware_type":"hat"},"channel":3,"sensor":"accelerometer",""" +
        """"sensor_config":{"sensitivity":100},"is_active":true,"last_seen_at":null,"stale_since":null}"""

    @Test fun devices_list_rename_group() = runBlocking {
        server.enqueue(json("[$device]"))
        val d = inst.devices.list().single()
        assertEquals("GET /api/installations/7/devices", server.takeRequest().let { "${it.method} ${it.path}" })
        assertEquals("waiting", d.groups.single().channels.single().state)
        assertEquals("https://x/t1/", d.tunnels.single().webUrl)
        assertNull(d.healthUrl)

        server.enqueue(json(device))
        inst.devices.rename(node, "Boiler")
        server.takeRequest().let {
            assertEquals("PATCH /api/installations/7/devices/$node", "${it.method} ${it.path}")
            assertEquals("""{"name":"Boiler"}""", it.body.readUtf8())
        }

        server.enqueue(json(device))
        inst.devices.updateGroup(node, group, buildJsonObject { put("interval", 120) })
        server.takeRequest().let {
            assertEquals("PATCH /api/installations/7/devices/$node/groups/$group", "${it.method} ${it.path}")
            assertEquals("""{"interval":120}""", it.body.readUtf8())
        }
    }

    @Test fun sources_crud() = runBlocking {
        server.enqueue(json("[$source]"))
        assertEquals(3, inst.sources.list(1).single().channel)
        assertEquals("/api/installations/7/measurement-points/1/sources", server.takeRequest().path)

        server.enqueue(json(source, 201))
        inst.sources.create(1, buildJsonObject { put("source_type", "mqtt"); put("mqtt_device_id", "SN-1") })
        server.takeRequest().let {
            assertEquals("POST", it.method)
            assertEquals("""{"source_type":"mqtt","mqtt_device_id":"SN-1"}""", it.body.readUtf8())
        }

        server.enqueue(json(source))
        inst.sources.update(1, src, buildJsonObject { put("sensitivity", 50) })
        assertEquals("PATCH /api/installations/7/measurement-points/1/sources/$src", server.takeRequest().let { "${it.method} ${it.path}" })

        server.enqueue(MockResponse().setResponseCode(204))
        inst.sources.delete(1, src)
        assertEquals("DELETE", server.takeRequest().method)

        assertThrows(ValidationException::class.java) { runBlocking { inst.sources.delete(1, "../x") } }
        Unit
    }

    @Test fun staff_tunnels_and_visitor_file() = runBlocking {
        server.enqueue(json("""[{"uuid":"$src","name":"ssh","label":"SSH","kind":"stcp","staff_only":true,"web_url":null,""" +
            """"local_port":22,"visitor_url":"https://x/v","installation_id":7,"installation_name":"Plant","node_uuid":"$node","device_name":"Node A"}]"""))
        val t = client.tunnels().single()
        assertEquals("/api/tunnels", server.takeRequest().path)
        assertEquals(22, t.localPort)
        assertEquals("Plant", t.installationName)

        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/toml").setBody("serverAddr = \"frp\"\n"))
        assertArrayEquals("serverAddr = \"frp\"\n".toByteArray(), client.tunnelVisitorFile(src))
        assertEquals("/api/tunnels/$src/visitor.toml", server.takeRequest().path)

        server.enqueue(json("""{"detail":"Staff only."}""", 403))
        assertThrows(AuthException::class.java) { runBlocking { client.tunnelVisitorFile(src) } }
        Unit
    }
}
