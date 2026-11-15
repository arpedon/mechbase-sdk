package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/** `assets.addPhoto` / `measurementPoints.addPhoto` (mechbase-web#405). */
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
}
