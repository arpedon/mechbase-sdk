import XCTest
@testable import Mechbase

final class OverviewTests: ParityTestCase {
    func testOverviewDecodesAndNulls() async throws {
        reply("OverviewOut")
        let o = try await inst.overview()
        XCTAssertEqual(method, "GET")
        XCTAssertEqual(url, "\(base)/overview")
        XCTAssertEqual(o.attention.first?.assetUuid, "6f1c0000-0000-4000-8000-00000000000a")
        XCTAssertEqual(o.runningExecutions.first?.executedBy?.id, 2)
        reply("OverviewOut", nulls: true)
        let n = try await inst.overview()
        XCTAssertNil(n.lastReadingAt)
        XCTAssertNil(n.briefing.silentSince)
    }

    func testAlertsQuery() async throws {
        reply("AlertOut", list: true)
        _ = try await inst.alerts()
        XCTAssertEqual(url, "\(base)/alerts")
        _ = try await inst.alerts(silentOnly: true)
        XCTAssertEqual(url, "\(base)/alerts?show=silent")
    }

    func testActivityPageQuery() async throws {
        reply("CursorPage_ActivityOut_")
        let page = try await inst.activity(cursor: "c1", limit: 20, sectionId: 3)
        XCTAssertEqual(url, "\(base)/activity?cursor=c1&limit=20&section_id=3")
        XCTAssertEqual(page.items.first?.kind, "status_change")
    }

    func testActivityFeedFollowsCursorsToTheEnd() async throws {
        let entry = #"{"kind":"comment","timestamp":"2026-11-27T10:00:00Z","title":"t","detail":"","state":"","severity":1,"actor":null,"old_status":null,"new_status":null,"asset_id":1,"point_id":null,"comment_id":4,"finding_uuid":null,"execution_uuid":null,"route_uuid":null}"#
        CaptureMock.queue = [#"{"items":[\#(entry),\#(entry)],"next_cursor":"p2"}"#, #"{"items":[\#(entry)],"next_cursor":null}"#]
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [CaptureMock.self]
        let inst = MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!,
                                  session: URLSession(configuration: cfg)).forInstallation(id: 7)
        var n = 0
        for try await e in inst.activityFeed(pageSize: 2) { XCTAssertEqual(e.commentId, 4); n += 1 }
        XCTAssertEqual(n, 3)
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/activity?cursor=p2&limit=2")
    }

    func testSearchHoursFlip() async throws {
        reply("SearchOut")
        let s = try await inst.search("pu mp", category: "assets")
        XCTAssertEqual(url, "\(base)/search?q=pu%20mp&in=assets")
        XCTAssertEqual(s.categories.first?.slug, "s")
        reply("HoursOut", nulls: true)
        let h = try await inst.hours(from: "2026-11-01", to: "2026-11-07")
        XCTAssertEqual(url, "\(base)/hours?production_from=2026-11-01&production_to=2026-11-07")
        XCTAssertNil(h.productionFrom)
        reply("ProductionStateOut")
        let p = try await inst.assets.flipProduction(assetId: 9)
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/assets/9/production/flip")
        XCTAssertEqual(p.state, "on")
    }

    func testNotificationSettings() async throws {
        reply("NotificationSettingsOut")
        let s = try await inst.notificationSettings()
        XCTAssertEqual(url, "\(base)/notification-settings")
        XCTAssertEqual(s.thresholdChoices.first?.value, 2)
        _ = try await inst.updateNotificationSettings(NotificationSettingsInput(severityThreshold: 3, notificationsMuted: true))
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(json.count, 2)
        XCTAssertEqual(json["severity_threshold"] as? Int, 3)
        XCTAssertEqual(json["notifications_muted"] as? Bool, true)
        reply("EmailTestOut")
        let r = try await inst.sendTestNotificationEmail()
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/notification-settings/test")
        XCTAssertEqual(r.result, "sent")
        ParityMock.reset(status: 502, reply: #"{"detail":"provider refused"}"#)
        await expectError({ _ = try await self.inst.sendTestNotificationEmail() }) {
            if case .server(502, _) = $0 { return true }; return false
        }
    }

    func testNonMemberIsAuthError() async {
        ParityMock.reset(status: 403, reply: #"{"detail":"Token not authorized for this installation."}"#)
        await expectError({ _ = try await self.inst.overview() }) {
            if case .auth(let m) = $0 { return m.contains("not authorized") }; return false
        }
    }
}
