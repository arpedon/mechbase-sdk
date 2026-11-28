package com.arpedon.mechbase

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneId

/** Account, push, notification settings, overview, alerts, activity, search, hours. */
class AccountOverviewTest : ApiTest() {
    private val me = """{"user":{"id":1,"username":"u","full_name":"U","email":"u@u","is_staff":true},""" +
        """"installations":[],"current_installation_id":null,"unit_prefs":{"acceleration":"g","velocity":"in/s",""" +
        """"temperature":"°F","pressure":"bar","frequency":"cpm"}}"""

    @Test fun x_timezone_is_sent_pinned_or_jvm_default() = runBlocking {
        reply(me)
        client.me()
        assertEquals("Europe/Athens", take().getHeader("X-Timezone"))

        val other = MockWebServer().apply { start() }
        try {
            other.enqueue(json(me))
            MechbaseClient(token = "t", baseUrl = other.url("/").toString()).me()
            assertEquals(ZoneId.systemDefault().id, other.takeRequest().getHeader("X-Timezone"))
        } finally { other.shutdown() }
    }

    @Test fun me_is_staff_and_patch() = runBlocking {
        reply(me)
        assertTrue(client.me().user.isStaff)
        take()
        // Older server: no is_staff → false.
        assertFalse(SDK_JSON.decodeFromString(User.serializer(), """{"id":1,"username":"u","full_name":"U"}""").isStaff)

        reply(me)
        client.updateMe(firstName = "Ann", unitPrefs = UnitPrefsUpdate(velocity = "in/s"))
        assertRequest("PATCH /api/me/", """{"first_name":"Ann","unit_prefs":{"velocity":"in/s"}}""")

        assertFails<ValidationException>(422) { client.updateMe(lastName = "") }
        Unit
    }

    @Test fun me_names_and_unit_choices() = runBlocking {
        reply("""{"user":{"id":1,"username":"u","full_name":"Ada L","first_name":"Ada","last_name":"L","email":"u@u"},""" +
            """"installations":[],"unit_choices":{"acceleration":[{"value":"g","label":"g"}],"velocity":[],""" +
            """"temperature":[{"value":"°F","label":"°F"}],"pressure":[],"frequency":[{"value":"Hz","label":"Hz"},{"value":"CPM","label":"CPM"}]}}""")
        val got = client.me()
        assertEquals("Ada", got.user.firstName)
        assertEquals("L", got.user.lastName)
        assertEquals(listOf("Hz", "CPM"), got.unitChoices!!.frequency.map { it.value })
        assertEquals("°F", got.unitChoices!!.temperature.single().label)
        // Older server: neither.
        reply(me)
        val old = client.me()
        assertEquals("", old.user.firstName)
        assertNull(old.unitChoices)
    }

    @Test fun web_session() = runBlocking {
        reply("""{"url":"https://x.test/auth/magic/abc/","expires_at":"2026-11-27T10:00:00Z"}""")
        val s = client.webSession("/2012/assets/5/")
        assertEquals("https://x.test/auth/magic/abc/", s.url)
        assertEquals("2026-11-27T10:00:00Z", s.expiresAt)
        assertRequest("POST /api/auth/web-session", """{"next":"/2012/assets/5/"}""")

        assertFails<ValidationException>(422) { client.webSession("//evil") }
        assertFails<AuthException>(403) { client.webSession("/") }
        Unit
    }

    @Test fun push_register_and_delete() = runBlocking {
        reply("""{"platform":"fcm","token":"abc:DEF","app_version":"1.2","created_at":"2026-01-01T00:00:00Z","last_seen_at":"2026-01-01T00:00:00Z"}""", 201)
        assertEquals("1.2", client.registerPushDevice("fcm", "abc:DEF", "1.2").appVersion)
        assertRequest("POST /api/push/devices", """{"platform":"fcm","token":"abc:DEF","app_version":"1.2"}""")

        noContent()
        client.deletePushDevice("abc:DEF/x")
        assertRequest("DELETE /api/push/devices/abc%3ADEF%2Fx")

        assertFails<NotFoundException>(404) { client.deletePushDevice("gone") }
        assertFails<AuthException>(403) { client.registerPushDevice("apns", "00") }
        Unit
    }

    @Test fun notification_settings() = runBlocking {
        val body = """{"severity_threshold":3,"status_changes":true,"route_completions":false,"exports":true,""" +
            """"notifications_muted":false,"threshold_choices":[{"value":3,"label":"Warning"}]}"""
        reply(body)
        assertEquals("Warning", inst.notificationSettings().thresholdChoices.single().label)
        assertRequest("GET /api/installations/7/notification-settings")

        reply(body)
        inst.updateNotificationSettings(notificationsMuted = true, severityThreshold = 4)
        assertRequest("PATCH /api/installations/7/notification-settings", """{"severity_threshold":4,"notifications_muted":true}""")

        reply("""{"result":"logged"}""")
        assertEquals("logged", inst.testNotificationEmail().result)
        assertRequest("POST /api/installations/7/notification-settings/test")

        assertFails<ServerException>(502) { inst.testNotificationEmail() }
        Unit
    }

    @Test fun overview_parses_nulls() = runBlocking {
        reply(
            """{"status_summary":{"total":5,"nominal":2,"elevated":1,"warning":1,"critical":1,"attention":3},""" +
                """"briefing":{"critical":1,"warning":1,"check":1,"silent":0,"silent_since":null,"normal":2,"attention":3,"last_reading":null},""" +
                """"last_reading_at":null,"attention":[{"section_id":null,"section_name":"","zone_id":null,"zone_name":null,""" +
                """"asset_id":4,"asset_uuid":"$u1","name":"Pump","status":4,"is_silent":false,"reason":"DE high","trigger_name":"DE",""" +
                """"trigger_point_id":null,"trigger_route":"","silent_points":[],"alert_since":null}],"attention_more_count":2,""" +
                """"silent_count":0,"running_executions":[{"execution_uuid":"$u2","route_uuid":"$u3","route_name":"Daily",""" +
                """"started_at":null,"executed_by":{"id":1,"name":"Ann"},"done":2,"total":9,"last_completed_execution_uuid":null}],""" +
                """"routes":[{"route_uuid":"$u3","name":"Daily","item_count":9,"last_run":null}],"back_to_normal":[],""" +
                """"sections":[{"section_id":1,"uuid":"$u1","name":"Hall","asset_count":5,"check_count":1,"warning_count":1,""" +
                """"critical_count":1,"worst_status":null}]}""",
        )
        val o = inst.overview()
        assertRequest("GET /api/installations/7/overview")
        assertEquals(2, o.attentionMoreCount)
        assertNull(o.attention.single().sectionId)
        assertEquals("Ann", o.runningExecutions.single().executedBy?.name)
        assertNull(o.routes.single().lastRun)
        assertNull(o.sections.single().worstStatus)
    }

    @Test fun alerts_activity_search_hours() = runBlocking {
        reply("[]")
        inst.alerts()
        assertRequest("GET /api/installations/7/alerts")
        reply("[]")
        inst.alerts(silentOnly = true)
        assertRequest("GET /api/installations/7/alerts?show=silent")

        reply(
            """{"items":[{"kind":"finding","timestamp":"2026-11-27T10:00:00+02:00","title":"t","detail":"","state":"open",""" +
                """"severity":3,"actor":null,"old_status":null,"new_status":null,"asset_id":4,"point_id":null,"comment_id":null,""" +
                """"finding_uuid":"$u1","execution_uuid":null,"route_uuid":null}],"next_cursor":"c2"}""",
        )
        val page = inst.activity(cursor = "c1", limit = 20, sectionId = 3)
        assertRequest("GET /api/installations/7/activity?cursor=c1&limit=20&section_id=3")
        assertEquals("c2", page.nextCursor)
        assertEquals(u1, page.items.single().findingUuid)
        reply("""{"items":[],"next_cursor":null}""")
        assertNull(inst.activity().nextCursor)
        assertRequest("GET /api/installations/7/activity")

        reply(
            """{"query":"pu","category":"assets","total_count":1,"categories":[{"key":"assets","slug":"assets","label":"Assets",""" +
                """"count":1,"selected":true}],"assets":[{"section_id":null,"section_name":"","zone_id":null,"zone_name":null,""" +
                """"asset_id":4,"uuid":"$u1","name":"Pump","status":1}],"sections":[],"zones":[],"points":[],"routes":[],""" +
                """"route_items":[],"comments":[],"item_responses":[]}""",
        )
        assertEquals("Pump", inst.search("pu", category = "assets").assets.single().name)
        assertRequest("GET /api/installations/7/search?q=pu&in=assets")

        reply(
            """{"production_from":"2026-11-01","production_to":null,"window_start":"2026-11-01T00:00:00+02:00",""" +
                """"window_end":"2026-11-27T12:00:00+02:00","stale_hours":2,"rows":[{"state":null,"last_ping":null,""" +
                """"section_id":null,"section_name":"","zone_id":null,"zone_name":null,"asset_id":4,"asset_uuid":"$u1",""" +
                """"asset_name":"Pump","point_id":9,"range_hours":12.5,"lifetime_hours":100.0,"segments":[{"start_pct":0,"width_pct":50.5}]}]}""",
        )
        val h = inst.hours(productionFrom = "2026-11-01")
        assertRequest("GET /api/installations/7/hours?production_from=2026-11-01")
        assertNull(h.rows.single().state)
        assertEquals(50.5, h.rows.single().segments.single().widthPct, 0.0)

        assertFails<AuthException>(403) { inst.overview() }
        Unit
    }

    @Test fun production_flip_and_checklist_rebuild() = runBlocking {
        reply("""{"state":"on","last_ping":"2026-11-27T10:00:00Z"}""")
        assertEquals("on", inst.assets.flipProduction(4).state)
        assertRequest("POST /api/installations/7/assets/4/production/flip")
        assertFails<ValidationException>(422) { inst.assets.flipProduction(4) }

        reply("""{"route_uuid":"$u1","created":false}""")
        assertFalse(inst.assets.rebuildChecklist(4).created)
        assertRequest("POST /api/installations/7/assets/4/checklist/rebuild")
        assertFails<NotFoundException>(404) { inst.assets.rebuildChecklist(5) }
        Unit
    }
}
