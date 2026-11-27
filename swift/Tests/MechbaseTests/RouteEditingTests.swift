import XCTest
@testable import Mechbase

final class RouteEditingTests: ParityTestCase {
    func testCreateRouteWithClientUUIDs() async throws {
        reply("RouteDetail", status: 201)
        let r = try await inst.routes.create(name: "Boiler house", items: [
            RouteItemInput(uuid: u2, label: "Leaks?"),
            RouteItemInput(uuid: u3, label: "DE bearing", itemType: "measurement", measurementPointId: 8),
        ], uuid: u1)
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/routes")
        XCTAssertEqual(json["uuid"] as? String, u1)
        XCTAssertEqual(json["description"] as? String, "")
        let items = json["items"] as? [[String: Any]]
        XCTAssertEqual(items?.first?["item_type"] as? String, "pass_fail")
        XCTAssertNil(items?.first?["asset_id"])
        XCTAssertEqual(items?.last?["measurement_point_id"] as? Int, 8)
        XCTAssertEqual(r.items.first?.checkId, 2)
        ParityMock.reset(status: 409, reply: #"{"detail":"uuid belongs to another route"}"#)
        await expectError({ _ = try await self.inst.routes.create(name: "x", items: [], uuid: self.u1) }) {
            if case .conflict = $0 { return true }; return false
        }
    }

    func testUpdateDeleteRoute() async throws {
        reply("RouteOut")
        _ = try await inst.routes.update(routeUUID: u1, name: "B2")
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(json as? [String: String], ["name": "B2"])
        ParityMock.reset(status: 204, reply: "")
        try await inst.routes.delete(routeUUID: u1)
        XCTAssertEqual(method, "DELETE")
        XCTAssertEqual(url, "\(base)/routes/\(u1)")
    }

    func testItemCRUD() async throws {
        reply("RouteItemOut", status: 201)
        _ = try await inst.routes.addItem(routeUUID: u1, RouteItemInput(uuid: u2, label: "Belts", itemType: "multi_check",
                                                                         subchecks: ["tension", "wear"], zoneId: 4))
        XCTAssertEqual(url, "\(base)/routes/\(u1)/items")
        XCTAssertEqual(json["subchecks"] as? [String], ["tension", "wear"])
        XCTAssertEqual(json["zone_id"] as? Int, 4)
        reply("RouteItemOut")
        _ = try await inst.routes.updateItem(routeUUID: u1, itemUUID: u2, RouteItemPatch(label: "Belt"))
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(url, "\(base)/routes/\(u1)/items/\(u2)")
        XCTAssertEqual(json as? [String: String], ["label": "Belt"])
        ParityMock.reset(status: 204, reply: "")
        try await inst.routes.deleteItem(routeUUID: u1, itemUUID: u2)
        XCTAssertEqual(method, "DELETE")
    }

    func testReorderTriState() async throws {
        reply("ReorderOut")
        let numbers = try await inst.routes.reorderItems(routeUUID: u1, [
            ReorderEntry(uuid: u2, position: 0),
            ReorderEntry(uuid: u3, position: 1, zoneId: 5, assetId: .some(nil)),
        ])
        XCTAssertEqual(url, "\(base)/routes/\(u1)/items/reorder")
        let items = json["items"] as? [[String: Any]]
        XCTAssertEqual(items?.first?.count, 2)  // zone/asset omitted: kept
        XCTAssertEqual(items?.last?["zone_id"] as? Int, 5)
        XCTAssertTrue(items?.last?["asset_id"] is NSNull)  // cleared
        XCTAssertEqual(numbers.first?.checkId, 2)
    }

    func testItemPhotoHistoryAndChecklistRebuild() async throws {
        reply("FileOut", status: 201)
        _ = try await inst.routes.setItemPhoto(routeUUID: u1, itemUUID: u2, photo: PhotoUpload(filename: "p.jpg", data: Data([9])), uuid: u3)
        XCTAssertEqual(url, "\(base)/routes/\(u1)/items/\(u2)/photos")
        XCTAssertEqual(formField("uuid"), u3)
        ParityMock.reset(status: 409, reply: #"{"detail":"superseded"}"#)
        await expectError({ _ = try await self.inst.routes.setItemPhoto(routeUUID: self.u1, itemUUID: self.u2,
                                                                       photo: PhotoUpload(filename: "p.jpg", data: Data()), uuid: self.u3) }) {
            if case .conflict = $0 { return true }; return false
        }
        reply("Page_ItemHistoryOut_", nulls: true)
        let h = try await inst.routes.itemHistory(routeUUID: u1, itemUUID: u2, limit: 10)
        XCTAssertEqual(url, "\(base)/routes/\(u1)/items/\(u2)/history?limit=10&offset=0")
        XCTAssertEqual(h.total, 2)
        reply("ChecklistOut")
        let c = try await inst.assets.rebuildChecklist(assetId: 6)
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/assets/6/checklist/rebuild")
        XCTAssertTrue(c.created)
    }
}
