import XCTest
@testable import Mechbase

final class RouteHistoryTests: ParityTestCase {
    func testExecutionsPageAndReport() async throws {
        reply("Page_ExecutionSummaryOut_")
        let page = try await inst.routes.executions(routeUUID: u1, limit: 20, offset: 40)
        XCTAssertEqual(url, "\(base)/routes/\(u1)/executions?limit=20&offset=40")
        XCTAssertEqual(page.total, 2)
        XCTAssertEqual(page.items.first?.executedBy?.name, "s")
        reply("ExecutionReportOut")
        let r = try await inst.routes.report(executionUUID: u2)
        XCTAssertEqual(url, "\(base)/executions/\(u2)/report")
        let resp = r.groups.first?.entries.first?.response
        XCTAssertEqual(resp?.photos.first?.kind, "s")
        XCTAssertEqual(resp?.reading?.pointSequence, 2)
        XCTAssertEqual(r.route.section?.name, "s")
        reply("ExecutionReportOut", nulls: true)
        let n = try await inst.routes.report(executionUUID: u2)
        XCTAssertNil(n.execution.executedBy)
        XCTAssertNil(n.execution.maxStatus)
    }

    func testResponseNotesNonConformitiesSurvey() async throws {
        reply("ItemResponseOut")
        _ = try await inst.routes.updateResponseNotes(responseUUID: u1, notes: "replace belt")
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(url, "\(base)/responses/\(u1)")
        XCTAssertEqual(json as? [String: String], ["notes": "replace belt"])
        reply("Page_NonConformityOut_", nulls: true)
        _ = try await inst.routes.nonConformities(status: "all", assetId: 4)
        XCTAssertEqual(url, "\(base)/non-conformities?status=all&asset_id=4&limit=50&offset=0")
        reply("NonConformityOut")
        let nc = try await inst.routes.resolveNonConformity(responseUUID: u1, comment: "fixed")
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/non-conformities/\(u1)/resolve")
        XCTAssertEqual(json as? [String: String], ["comment": "fixed"])
        XCTAssertEqual(nc.resolvedBy?.id, 2)
        ParityMock.reset(status: 409, reply: #"{"detail":"Resolved by someone else."}"#)
        await expectError({ _ = try await self.inst.routes.resolveNonConformity(responseUUID: self.u1) }) {
            if case .conflict = $0 { return true }; return false
        }
        reply("SurveyOut", status: 201)
        let s = try await inst.routes.startSurvey(name: "Walkdown", uuid: u3)
        XCTAssertEqual(url, "\(base)/surveys")
        XCTAssertEqual(json as? [String: String], ["name": "Walkdown", "uuid": u3])
        XCTAssertEqual(s.execution.status, "s")
    }

    func testAmendAnswerAndNotes() async throws {
        let exec = inst.routes.execution(uuid: u1)
        reply("ItemResponseOut", status: 201)
        _ = try await exec.amendAnswer(itemUUID: u2, data: .object(["passed": .bool(false)]), notes: "leak",
                                       idempotencyKey: "k-1")
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/executions/\(u1)/amend/\(u2)/answer")
        XCTAssertEqual(header("X-Idempotency-Key"), "k-1")
        XCTAssertEqual(json["data"] as? [String: Bool], ["passed": false])
        XCTAssertEqual(json["notes"] as? String, "leak")
        _ = try await exec.amendNotes(itemUUID: u2, notes: "")
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(url, "\(base)/executions/\(u1)/amend/\(u2)/notes")
        XCTAssertNil(header("X-Idempotency-Key"))
    }

    func testAmendPhotosAndReading() async throws {
        let exec = inst.routes.execution(uuid: u1)
        reply("FileOut", status: 201)
        _ = try await exec.amendAddPhoto(itemUUID: u2, photo: PhotoUpload(filename: "a.jpg", data: Data([1])), uuid: u3)
        XCTAssertEqual(url, "\(base)/executions/\(u1)/amend/\(u2)/photos")
        XCTAssertTrue(header("Content-Type")?.hasPrefix("multipart/form-data") ?? false)
        XCTAssertEqual(formField("uuid"), u3)
        XCTAssertTrue(bodyText.contains(#"name="file"; filename="a.jpg""#))
        ParityMock.reset(status: 204, reply: "")
        try await exec.amendRemovePhoto(itemUUID: u2, fileUUID: u3)
        XCTAssertEqual(method, "DELETE")
        XCTAssertEqual(url, "\(base)/executions/\(u1)/amend/\(u2)/photos/\(u3)")
        reply("ItemResponseOut", status: 201)
        _ = try await exec.amendReading(itemUUID: u2, value: 4.2, comment: "re-measured",
                                        images: [PhotoUpload(filename: "1.jpg", data: Data([1])), PhotoUpload(filename: "2.jpg", data: Data([2]))],
                                        dataFile: PhotoUpload(filename: "w.dr", mimeType: "application/octet-stream", data: Data([3])),
                                        idempotencyKey: "k-2")
        XCTAssertEqual(url, "\(base)/executions/\(u1)/amend/\(u2)/reading")
        XCTAssertEqual(header("X-Idempotency-Key"), "k-2")
        XCTAssertEqual(formField("value"), "4.2")
        XCTAssertEqual(formField("comment"), "re-measured")
        XCTAssertEqual(bodyText.components(separatedBy: #"name="images""#).count - 1, 2)
        XCTAssertTrue(bodyText.contains(#"name="data_file"; filename="w.dr""#))
        ParityMock.reset(status: 409, reply: #"{"detail":"Idempotency key used by another reading."}"#)
        await expectError({ _ = try await exec.amendReading(itemUUID: self.u2, value: 1, idempotencyKey: "k-2") }) {
            if case .conflict = $0 { return true }; return false
        }
    }

    func testAmendRejectsNonUUIDWithoutRequest() async {
        await expectError({ _ = try await self.inst.routes.execution(uuid: "x/../y").amendNotes(itemUUID: self.u2, notes: "") }) {
            if case .validation = $0 { return true }; return false
        }
        XCTAssertNil(ParityMock.request)
    }
}
