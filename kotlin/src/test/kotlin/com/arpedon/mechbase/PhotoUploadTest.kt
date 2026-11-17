package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/** Asset/point photos: `addPhoto` writes, `imageUrls` reads (mechbase-web#405). */
class PhotoUploadTest {
    private lateinit var server: MockWebServer
    private lateinit var client: MechbaseClient

    @Before fun setUp() {
        server = MockWebServer(); server.start()
        client = MechbaseClient(token = "tok", baseUrl = server.url("/").toString().trimEnd('/'))
    }
    @After fun tearDown() { server.shutdown() }

    private fun enqueueFile() = server.enqueue(
        MockResponse().setResponseCode(201).setHeader("Content-Type", "application/json").setBody(
            """{"uuid":"f1","name":"p.jpg","kind":"attachment","file_url":"https://x/p.jpg","created_at":"2026-01-01T00:00:00Z"}""",
        ),
    )

    private fun jpg() = File.createTempFile("photo", ".jpg").apply { writeBytes(byteArrayOf(1, 2)); deleteOnExit() }

    @Test fun asset_photo_posts_file_and_uuid() = runBlocking {
        enqueueFile()
        val out = client.forInstallation(2012).assets.addPhoto(10, jpg(), uuid = "u-1")
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/assets/10/photos/", rec.path)
        val body = rec.body.readUtf8()
        assertTrue(body.contains("name=\"uuid\""))
        assertTrue(body.contains("u-1"))
        assertTrue(body.contains("name=\"file\""))
        assertEquals("f1", out.uuid)
    }

    @Test fun point_photo_without_uuid_sends_no_uuid_part() = runBlocking {
        enqueueFile()
        client.forInstallation(2012).measurementPoints.addPhoto(44, jpg())
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/measurement-points/44/photos/", rec.path)
        assertFalse(rec.body.readUtf8().contains("name=\"uuid\""))
    }

    @Test fun measurement_file_posts_uuid() = runBlocking {
        enqueueFile()
        client.forInstallation(2012).measurements.addFile("m-1", jpg(), uuid = "u-2")
        val rec = server.takeRequest()
        assertEquals("/api/installations/2012/measurements/m-1/files/", rec.path)
        val body = rec.body.readUtf8()
        assertTrue(body.contains("name=\"uuid\""))
        assertTrue(body.contains("u-2"))
    }

    @Test fun image_urls_decode_and_default_empty() {
        val asset = SDK_JSON.decodeFromString(
            Asset.serializer(),
            """{"uuid":"a","name":"Pump","status":1,"image_urls":["https://x/a.jpg"]}""",
        )
        val point = SDK_JSON.decodeFromString(MeasurementPoint.serializer(), """{"uuid":"p","name":"DE","status":1}""")
        assertEquals(listOf("https://x/a.jpg"), asset.imageUrls)
        assertEquals(emptyList<String>(), point.imageUrls)
    }

    @Test fun photos_decode_and_default_empty() {
        val asset = SDK_JSON.decodeFromString(
            Asset.serializer(),
            """{"uuid":"a","name":"Pump","status":1,"image_urls":["https://x/a.jpg"],"photos":[{"uuid":"f1","url":"https://x/a.jpg"}]}""",
        )
        val point = SDK_JSON.decodeFromString(MeasurementPoint.serializer(), """{"uuid":"p","name":"DE","status":1}""")
        assertEquals(listOf(Photo("f1", "https://x/a.jpg")), asset.photos)
        assertEquals(emptyList<Photo>(), point.photos)
    }

    @Test fun delete_photo_hits_delete_on_photo_path() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(204))
        server.enqueue(MockResponse().setResponseCode(204))
        client.forInstallation(2012).assets.deletePhoto(10, "f1")
        client.forInstallation(2012).measurementPoints.deletePhoto(44, "f2")
        val a = server.takeRequest()
        val p = server.takeRequest()
        assertEquals("DELETE /api/installations/2012/assets/10/photos/f1", "${a.method} ${a.path}")
        assertEquals("DELETE /api/installations/2012/measurement-points/44/photos/f2", "${p.method} ${p.path}")
    }

    @Test fun delete_photo_404_is_not_found() {
        repeat(2) { server.enqueue(MockResponse().setResponseCode(404).setBody("""{"detail":"Not Found"}""")) }
        val inst = client.forInstallation(1)
        assertThrows(NotFoundException::class.java) { runBlocking { inst.assets.deletePhoto(10, "gone") } }
        assertThrows(NotFoundException::class.java) { runBlocking { inst.measurementPoints.deletePhoto(44, "gone") } }
    }
}
