import XCTest
@testable import Mechbase

/// The gaps the app lanes found: reading get/delete, error detail, finding → reading, retry-safe
/// comments, asset-scoped activity, inherited documents, asset production state.
final class AppGapsTests: ParityTestCase {
    func testReadingGetAndDelete() async throws {
        reply("MeasurementOut")
        let m = try await inst.measurements.get(pointId: 2, pointSequence: 766)
        XCTAssertEqual(method, "GET")
        XCTAssertEqual(url, "\(base)/measurement-points/2/measurements/766/")
        XCTAssertEqual(m.pointSequence, 2)

        ParityMock.reset(reply: #"{"deleted":true,"uuid":"\#(u1)"}"#)
        let d = try await inst.measurements.delete(pointId: 2, pointSequence: 766)
        XCTAssertEqual(method, "DELETE")
        XCTAssertEqual(url, "\(base)/measurement-points/2/measurements/766/")
        XCTAssertTrue(d.deleted)

        ParityMock.reset(status: 404, reply: #"{"detail":"Not Found"}"#)
        await expectError({ _ = try await self.inst.measurements.get(pointId: 2, pointSequence: 1) }) {
            if case .notFound = $0 { return true }; return false
        }
    }

    func testErrorDetailDropsTheStatus() async {
        ParityMock.reset(status: 422, reply: #"{"detail":"next: must be a path on this site."}"#)
        await expectError({ _ = try await self.client.webSession(next: "//x") }) {
            $0.detail == "next: must be a path on this site."
        }
        ParityMock.reset(status: 409, reply: #"{"detail":"That uuid belongs to another comment."}"#)
        await expectError({ _ = try await self.inst.comments.create(assetId: 1, body: "x", uuid: self.u1) }) {
            $0.detail == "That uuid belongs to another comment."
        }
        XCTAssertNil(MechbaseError.transport(URLError(.timedOut)).detail)
        XCTAssertEqual(MechbaseError.validation("no status here").detail, "no status here")
    }

    func testFindingLinksToItsReading() async throws {
        reply("FindingOut")
        let full = try await inst.findings.get(uuid: u1)
        XCTAssertEqual(full.pointSequence, 2)
        reply("FindingOut", nulls: true)
        let bare = try await inst.findings.get(uuid: u1)
        XCTAssertNil(bare.pointSequence)
    }

    func testCommentCreateSendsClientUuidOnlyWhenGiven() async throws {
        ParityMock.reset(status: 201, reply: #"{"id":5,"uuid":"\#(u1)","body":"b","references":[]}"#)
        let c = try await inst.comments.create(assetId: 1, body: "b", uuid: u1)
        XCTAssertEqual(json["uuid"] as? String, u1)
        XCTAssertEqual(c.uuid, u1)
        ParityMock.reset(status: 201, reply: #"{"id":6,"body":"b","references":[]}"#)
        let plain = try await inst.comments.create(assetId: 1, body: "b")
        XCTAssertNil(json["uuid"])
        XCTAssertNil(plain.uuid)
    }

    func testActivityByAsset() async throws {
        ParityMock.reset(reply: #"{"items":[],"next_cursor":null}"#)
        _ = try await inst.activity(assetId: 4)
        XCTAssertEqual(URLComponents(string: url!)?.queryItems?.first { $0.name == "asset_id" }?.value, "4")
    }

    func testDocumentsInheritedAndAssetProductionState() async throws {
        ParityMock.reset(reply: #"[{"uuid":"\#(u1)","name":"a","kind":"manual","url":"u","created_at":"t","inherited":true},{"uuid":"\#(u2)","name":"b","kind":"drawing","url":"u","created_at":"t"}]"#)
        let docs = try await inst.documents.list(assetId: 1)
        XCTAssertEqual(docs.map(\.inherited), [true, false])

        ParityMock.reset(reply: #"{"uuid":"\#(u1)","asset_id":1,"name":"P","section_id":1,"zone_id":null,"status":1,"running":"on","running_since":"2026-11-27T10:00:00Z"}"#)
        let a = try await inst.assets.get(id: 1)
        XCTAssertEqual(a.running, "on")
        XCTAssertEqual(a.runningSince, "2026-11-27T10:00:00Z")
        ParityMock.reset(reply: #"{"uuid":"\#(u1)","asset_id":1,"name":"P","section_id":1,"zone_id":null,"status":1}"#)
        let untracked = try await inst.assets.get(id: 1)
        XCTAssertNil(untracked.running)
    }

    func testActivityTriggerAndKind() async throws {
        ParityMock.reset(reply: #"{"items":[{"kind":"status_change","timestamp":"t","title":"x","detail":"d","state":"Warning","severity":3,"trigger_type":"measurement","measured_at":"2026-11-27T08:00:00Z"},{"kind":"comment","timestamp":"t","title":"y","detail":"d","state":"Note","severity":0}],"next_cursor":null}"#)
        let page = try await inst.activity(assetId: 4, kind: .statusChange)
        let q = URLComponents(string: url!)?.queryItems ?? []
        XCTAssertEqual(q.first { $0.name == "kind" }?.value, "status_change")
        XCTAssertEqual(page.items[0].triggerType, "measurement")
        XCTAssertEqual(page.items[0].measuredAt, "2026-11-27T08:00:00Z")
        XCTAssertNil(page.items[1].measuredAt)
        _ = try await inst.activity()
        XCTAssertNil(URLComponents(string: url!)?.queryItems?.first { $0.name == "kind" }?.value)
    }

    func testAddFieldItemSendsClientUuidOnlyWhenGiven() async throws {
        let exec = inst.routes.execution(uuid: u1)
        reply("ItemResponseOut", status: 201)
        _ = try await exec.addFieldItem(label: "Leak", uuid: u2.uppercased())
        XCTAssertEqual(url, "\(base)/executions/\(u1)/items")
        XCTAssertEqual(json["uuid"] as? String, u2)  // lowercased, as the server echoes it
        reply("ItemResponseOut", status: 201)
        _ = try await exec.addFieldItem(label: "Leak", data: ["passed": false])
        XCTAssertNil(json["uuid"])
        ParityMock.reset(status: 409, reply: #"{"detail":"That uuid belongs to another route item."}"#)
        await expectError({ _ = try await exec.addFieldItem(label: "x", uuid: self.u3) }) {
            $0.detail == "That uuid belongs to another route item."
        }
    }

    func testRouteAssetChecksFor() async throws {
        ParityMock.reset(reply: #"{"uuid":"\#(u1)","name":"Pump checks","description":"","asset_checks_for":4,"items":[]}"#)
        let detail = try await inst.routes.detail(routeUUID: u1)
        XCTAssertEqual(detail.assetChecksFor, 4)
        ParityMock.reset(reply: #"{"items":[{"uuid":"\#(u1)","name":"Daily","description":""}],"total":1,"limit":50,"offset":0}"#)
        let routes = try await inst.routes.list()
        XCTAssertNil(routes.first?.assetChecksFor)
        XCTAssertNil(URLComponents(string: url!)?.queryItems?.first { $0.name == "include_asset_checks" })
        ParityMock.reset(reply: #"{"items":[{"uuid":"\#(u1)","name":"Pump checks","description":"","asset_checks_for":4}],"total":1,"limit":50,"offset":0}"#)
        let all = try await inst.routes.list(includeAssetChecks: true)
        XCTAssertEqual(URLComponents(string: url!)?.queryItems?.first { $0.name == "include_asset_checks" }?.value, "true")
        XCTAssertEqual(all.first?.assetChecksFor, 4)
    }

    func testRouteItemInstructionsUnitSubchecks() async throws {
        ParityMock.reset(reply: #"{"uuid":"\#(u1)","name":"R","description":"","items":[{"uuid":"\#(u2)","check_id":1,"label":"Casing","item_type":"multi_check","config":{"checks":[{"label":"Seal"}]},"instructions":["legacy"],"instructions_html":"<div>Hold</div>","has_own_instructions":true,"unit":"","subchecks":["Seal"]},{"uuid":"\#(u3)","check_id":2,"label":"Old","item_type":"pass_fail","config":{}}]}"#)
        let items = try await inst.routes.detail(routeUUID: u1).items
        XCTAssertEqual(items[0].instructionsHtml, "<div>Hold</div>")
        XCTAssertTrue(items[0].hasOwnInstructions)
        XCTAssertEqual(items[0].subchecks, ["Seal"])
        XCTAssertEqual(items[0].instructions, ["legacy"])
        XCTAssertEqual(items[1].instructionsHtml, "")  // an older server
        XCTAssertFalse(items[1].hasOwnInstructions)
        XCTAssertEqual(items[1].unit, "")
    }

    func testReportCheckAndNonConformityFields() throws {
        let check = try JSONDecoder().decode(ReportCheck.self, from: Data(#"{"uuid":"\#(u1)","check_id":1,"label":"Casing","item_type":"measurement","asset_id":1,"asset_name":"Pump","zone_id":1,"measurement_point_id":1,"config":{},"instructions":"<div>Probe</div>","limit":{"minor":60,"major":80,"direction":"high","unit":"°C"}}"#.utf8))
        XCTAssertEqual(check.instructions, "<div>Probe</div>")
        XCTAssertEqual(check.limit?.major, 80)
        let old = try JSONDecoder().decode(ReportCheck.self, from: Data(#"{"uuid":"\#(u1)","check_id":1,"label":"G","item_type":"pass_fail","asset_id":null,"asset_name":null,"zone_id":null,"measurement_point_id":null,"config":{}}"#.utf8))
        XCTAssertNil(old.instructions)
        let nc = try JSONDecoder().decode(NonConformity.self, from: Data(#"{"response_uuid":"a","execution_uuid":"b","route_uuid":"c","route_name":"W","route_item_uuid":"d","label":"Guard","asset_id":1,"asset_name":"Pump","status":3,"notes":"","started_at":null,"created_at":"t","resolved_at":null,"resolved_by":null,"resolution_comment":""}"#.utf8))
        XCTAssertEqual(nc.assetName, "Pump")
    }
}
