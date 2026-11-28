import XCTest
@testable import Mechbase

final class DashboardsTests: ParityTestCase {
    func testDefaultBoardReturnsBodyAndEtag() async throws {
        reply("DashboardOut")
        ParityMock.headers = ["ETag": #"W/"abc""#]
        let r = try await inst.dashboards.get()
        XCTAssertEqual(url, "\(base)/dashboards/default")
        XCTAssertNil(header("If-None-Match"))
        XCTAssertEqual(ParityMock.request?.cachePolicy, .reloadIgnoringLocalCacheData)
        guard case .modified(let board, let etag) = r else { return XCTFail("want modified") }
        XCTAssertEqual(etag, #"W/"abc""#)
        XCTAssertEqual(board.sections.first?.tiles.first?.trend?.points.first?.v, 1.5)
        XCTAssertEqual(board.sections.first?.tiles.first?.timeline?.first?.isOpen, true)
    }

    func testNotModifiedEchoesEtagVerbatim() async throws {
        ParityMock.reset(status: 304, reply: "", headers: ["ETag": #"W/"abc""#])
        let r = try await inst.dashboards.get(dashboardUuid: u1, etag: #"W/"abc""#)
        XCTAssertEqual(url, "\(base)/dashboards/\(u1)")
        XCTAssertEqual(header("If-None-Match"), #"W/"abc""#)
        guard case .notModified = r else { return XCTFail("want notModified") }
        XCTAssertNil(r.value)
    }

    func testBoardWithNullsAndErrors() async throws {
        reply("DashboardOut", nulls: true)
        let board = try await inst.dashboards.get().value
        XCTAssertNil(board?.uuid)
        ParityMock.reset(status: 404, reply: #"{"detail":"Not found"}"#)
        await expectError({ _ = try await self.inst.dashboards.get(dashboardUuid: self.u1) }) {
            if case .notFound = $0 { return true }; return false
        }
        await expectError({ _ = try await self.inst.dashboards.get(dashboardUuid: "default/../x") }) {
            if case .validation = $0 { return true }; return false
        }
    }

    func testStaffEdits() async throws {
        reply("DashboardSummaryOut", list: true)
        _ = try await inst.dashboards.list()
        XCTAssertEqual(url, "\(base)/dashboards")
        reply("DashboardSummaryOut", status: 201)
        _ = try await inst.dashboards.create(name: "Boilers")
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(json["name"] as? String, "Boilers")
        _ = try await inst.dashboards.update(dashboardUuid: u1, isDefault: true)
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(json as? [String: Bool], ["is_default": true])
        _ = try await inst.dashboards.saveAutomatic()
        XCTAssertEqual(url, "\(base)/dashboards/save-automatic")
        ParityMock.reset(status: 204, reply: "")
        try await inst.dashboards.reorder(dashboardUuid: u1, sections: [LayoutSection(id: u2, tiles: [u3])])
        XCTAssertEqual(url, "\(base)/dashboards/\(u1)/reorder")
        XCTAssertEqual((json["sections"] as? [[String: Any]])?.first?["tiles"] as? [String], [u3])
        try await inst.dashboards.delete(dashboardUuid: u1)
        XCTAssertEqual(method, "DELETE")
    }

    func testSectionsAndTiles() async throws {
        reply("DashboardSectionOut", status: 201)
        let s = try await inst.dashboards.addSection(dashboardUuid: u1, title: "Pumps")
        XCTAssertEqual(url, "\(base)/dashboards/\(u1)/sections")
        XCTAssertEqual(s.position, 2)
        _ = try await inst.dashboards.renameSection(dashboardUuid: u1, sectionUuid: u2, title: "P")
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(url, "\(base)/dashboards/\(u1)/sections/\(u2)")
        reply("TileRefOut", status: 201, list: true)
        let tiles = try await inst.dashboards.addTiles(dashboardUuid: u1, sectionUuid: u2, pointIds: [4, 5])
        XCTAssertEqual(json["point_ids"] as? [Int], [4, 5])
        XCTAssertEqual(json["section"] as? String, u2)
        XCTAssertEqual(tiles.first?.customLabel, "s")
        reply("TileRefOut")
        _ = try await inst.dashboards.renameTile(dashboardUuid: u1, tileUuid: u3, label: "")
        XCTAssertEqual(url, "\(base)/dashboards/\(u1)/tiles/\(u3)")
        XCTAssertEqual(json["label"] as? String, "")
        ParityMock.reset(status: 204, reply: "")
        try await inst.dashboards.removeTile(dashboardUuid: u1, tileUuid: u3)
        try await inst.dashboards.deleteSection(dashboardUuid: u1, sectionUuid: u2)
        XCTAssertEqual(url, "\(base)/dashboards/\(u1)/sections/\(u2)")
        ParityMock.reset(status: 422, reply: #"{"detail":"sections: point twice"}"#)
        await expectError({ try await self.inst.dashboards.reorder(dashboardUuid: self.u1, sections: []) }) {
            if case .validation = $0 { return true }; return false
        }
    }
}
