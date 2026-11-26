import XCTest
@testable import Mechbase

/// Comments, documents and alarm rules: method, path, body, decode.
final class CommentsDocumentsAlarmsTests: XCTestCase {
    private func client(_ mock: AnyClass = CaptureMock.self) -> MechbaseClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [mock]
        return MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
    }
    private var inst: Installation { client().forInstallation(id: 7) }
    private let base = "https://x.test/api/installations/7"
    private let rid = "6f1c0000-0000-4000-8000-000000000001"

    private let comment = #"{"id":9,"body":"<p>x</p>","body_text":"x","author_name":"A","created_at":"2026-01-01T00:00:00Z","edited_at":null,"references":[{"point_id":5,"point_sequence":null}],"is_finding":false,"editable":true}"#
    private var rule: String { #"{"uuid":"\#(rid)","scope":"point","method":"threshold","data_key":"","effective_data_key":"velocity","direction":"high","minor_threshold":2.5,"major_threshold":null,"threshold_mode":"absolute","source":null}"# }

    func testCommentsList() async throws {
        CaptureMock.reply = #"{"items":[\#(comment)],"total":21,"limit":10,"offset":20}"#
        let page = try await inst.comments.list(assetId: 3, limit: 10, offset: 20)
        XCTAssertEqual(CaptureMock.lastMethod, "GET")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/assets/3/comments?limit=10&offset=20")
        XCTAssertEqual(page.total, 21)
        XCTAssertNil(page.items[0].editedAt)
        XCTAssertEqual(page.items[0].references, [CommentReference(pointId: 5, pointSequence: nil)])
    }

    func testCommentsCreate() async throws {
        CaptureMock.reply = comment
        let c = try await inst.comments.create(assetId: 3, body: "hi", references: [CommentReferenceIn(pointId: 5, pointSequence: 2)])
        XCTAssertEqual(CaptureMock.lastMethod, "POST")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/assets/3/comments")
        XCTAssertEqual(CaptureMock.lastJSON?["body"] as? String, "hi")
        let ref = (CaptureMock.lastJSON?["references"] as? [[String: Any]])?.first
        XCTAssertEqual(ref?["point_id"] as? Int, 5)
        XCTAssertEqual(ref?["point_sequence"] as? Int, 2)
        XCTAssertTrue(c.editable)
    }

    func testCommentsUpdateSendsEmptyReferenceSet() async throws {
        CaptureMock.reply = comment
        _ = try await inst.comments.update(assetId: 3, commentId: 9, body: "yo")
        XCTAssertEqual(CaptureMock.lastMethod, "PATCH")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/assets/3/comments/9")
        XCTAssertEqual(CaptureMock.lastJSON?["body"] as? String, "yo")
        XCTAssertEqual((CaptureMock.lastJSON?["references"] as? [Any])?.count, 0)
    }

    func testCommentsDelete() async throws {
        CaptureMock.reply = "{}"
        try await inst.comments.delete(assetId: 3, commentId: 9)
        XCTAssertEqual(CaptureMock.lastMethod, "DELETE")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/assets/3/comments/9")
    }

    func testDocumentsList() async throws {
        CaptureMock.reply = #"[{"uuid":"d1","name":"a.pdf","kind":"manual","url":"/d","created_at":"2026-01-01T00:00:00Z"}]"#
        let l = try await inst.documents.list(assetId: 3)
        XCTAssertEqual(CaptureMock.lastMethod, "GET")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/assets/3/documents")
        XCTAssertEqual(l.first?.kind, "manual")
    }

    func testDocumentsAddPostsMultipart() async throws {
        let d = try await client(PhotoMock.self).forInstallation(id: 7).documents.add(assetId: 3, file: Data("PDF".utf8), kind: "manual", uuid: "d1")
        XCTAssertEqual(PhotoMock.lastPath, "\(base)/assets/3/documents")
        XCTAssertTrue(PhotoMock.lastBody.contains("name=\"kind\"\r\n\r\nmanual\r\n"), PhotoMock.lastBody)
        XCTAssertTrue(PhotoMock.lastBody.contains("name=\"uuid\"\r\n\r\nd1\r\n"), PhotoMock.lastBody)
        XCTAssertTrue(PhotoMock.lastBody.contains("filename=\"document.pdf\""), PhotoMock.lastBody)
        XCTAssertTrue(PhotoMock.lastBody.contains("PDF"))
        XCTAssertEqual(d.uuid, "f1")
    }

    func testDocumentsDelete() async throws {
        CaptureMock.reply = "{}"
        try await inst.documents.delete(assetId: 3, uuid: rid)
        XCTAssertEqual(CaptureMock.lastMethod, "DELETE")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/assets/3/documents/\(rid)")
    }

    func testAlarmRulesList() async throws {
        CaptureMock.reply = "[\(rule)]"
        let l = try await inst.alarmRules.list(pointId: 5)
        XCTAssertEqual(CaptureMock.lastMethod, "GET")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/measurement-points/5/alarm-rules")
        XCTAssertEqual(l[0].scope, "point")
        XCTAssertEqual(l[0].minorThreshold, 2.5)
        XCTAssertNil(l[0].majorThreshold)
        XCTAssertNil(l[0].source)
    }

    func testAlarmRulesCreate() async throws {
        CaptureMock.reply = rule
        _ = try await inst.alarmRules.create(pointId: 5, minorThreshold: 2.5, majorThreshold: 4)
        XCTAssertEqual(CaptureMock.lastMethod, "POST")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/measurement-points/5/alarm-rules")
        XCTAssertEqual(CaptureMock.lastJSON?["method"] as? String, "threshold")
        XCTAssertEqual(CaptureMock.lastJSON?["data_key"] as? String, "")
        XCTAssertEqual(CaptureMock.lastJSON?["direction"] as? String, "high")
        XCTAssertEqual(CaptureMock.lastJSON?["minor_threshold"] as? Double, 2.5)
        XCTAssertEqual(CaptureMock.lastJSON?["major_threshold"] as? Double, 4)
    }

    func testAlarmRulesUpdateSendsOnlyGivenFields() async throws {
        CaptureMock.reply = rule
        _ = try await inst.alarmRules.update(pointId: 5, uuid: rid, majorThreshold: 6)
        XCTAssertEqual(CaptureMock.lastMethod, "PATCH")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/measurement-points/5/alarm-rules/\(rid)")
        XCTAssertEqual(Set(CaptureMock.lastJSON?.keys.map { $0 } ?? []), ["major_threshold"])
        XCTAssertEqual(CaptureMock.lastJSON?["major_threshold"] as? Double, 6)
    }

    func testAlarmRulesDelete() async throws {
        CaptureMock.reply = "{}"
        try await inst.alarmRules.delete(pointId: 5, uuid: rid)
        XCTAssertEqual(CaptureMock.lastMethod, "DELETE")
        XCTAssertEqual(CaptureMock.lastPath, "\(base)/measurement-points/5/alarm-rules/\(rid)")
    }
}
