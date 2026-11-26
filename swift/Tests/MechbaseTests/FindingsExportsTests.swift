import XCTest
@testable import Mechbase

/// Findings, analytics exports, token revoke and hotspot edit: method, path, body, decode.
final class FindingsExportsTests: XCTestCase {
    private func client() -> MechbaseClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [CaptureMock.self]
        return MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
    }

    private let finding = #"{"uuid":"f-1","status":"open","fault_type":"imb","fault_type_display":"Imbalance","severity":"major","recommended_action":"balance","due_by":"2026-12-01","comment":"","evidence":{"a":1},"work_order_ref":"WO-9","acknowledged_at":null,"closed_at":null,"created_at":"2026-11-01T00:00:00Z","updated_at":"2026-11-01T00:00:00Z","created_by":null,"asset_id":3,"asset_external_id":"A-3","asset_name":"Pump","point_id":5,"point_external_id":null,"point_name":"DE","point_location":"x","measurement_uuid":null,"measurement_external_id":null,"measurement_timestamp":null,"web_url":"https://w"}"#

    func testFindingsListSendsFiltersAndDecodes() async throws {
        CaptureMock.reply = #"{"items":[\#(finding)],"next_cursor":"c2"}"#
        let page = try await client().forInstallation(id: 2012).findings.list(cursor: "c1", limit: 10, status: "open", assetId: 3)
        XCTAssertEqual(CaptureMock.lastMethod, "GET")
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/installations/2012/findings/?cursor=c1&limit=10&status=open&asset_id=3")
        XCTAssertEqual(page.nextCursor, "c2")
        XCTAssertEqual(page.items.first?.assetExternalId, "A-3")
    }

    func testFindingGet() async throws {
        CaptureMock.reply = finding
        let f = try await client().forInstallation(id: 2012).findings.get(uuid: "f-1")
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/installations/2012/findings/f-1/")
        XCTAssertEqual(f.faultTypeDisplay, "Imbalance")
    }

    func testFindingSetStatusPostsBody() async throws {
        CaptureMock.reply = finding
        let f = try await client().forInstallation(id: 2012).findings.setStatus(uuid: "f-1", status: "acknowledged", workOrderRef: "WO-9")
        XCTAssertEqual(CaptureMock.lastMethod, "POST")
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/installations/2012/findings/f-1/status/")
        XCTAssertEqual(CaptureMock.lastJSON?["status"] as? String, "acknowledged")
        XCTAssertEqual(CaptureMock.lastJSON?["work_order_ref"] as? String, "WO-9")
        XCTAssertEqual(f.workOrderRef, "WO-9")
    }

    func testExportCreatePostsAndDecodes() async throws {
        CaptureMock.reply = #"{"job_uuid":"j-1","state":"queued","status_url":"/s"}"#
        let job = try await client().forInstallation(id: 2012).exports.create(dataset: "findings", filters: ExportFilters(assetId: 3))
        XCTAssertEqual(CaptureMock.lastMethod, "POST")
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/installations/2012/analytics/exports/")
        XCTAssertEqual(CaptureMock.lastJSON?["dataset"] as? String, "findings")
        XCTAssertEqual(CaptureMock.lastJSON?["format"] as? String, "csv")
        XCTAssertEqual((CaptureMock.lastJSON?["filters"] as? [String: Any])?["asset_id"] as? Int, 3)
        XCTAssertEqual(job.jobUuid, "j-1")
    }

    func testExportStatusDecodes() async throws {
        CaptureMock.reply = #"{"job_uuid":"j-1","dataset":"findings","file_format":"csv","state":"done","row_count":4,"byte_size":120,"download_url":"/d?sig=z","expires_at":null,"created_at":"2026-11-01T00:00:00Z"}"#
        let st = try await client().forInstallation(id: 2012).exports.status(jobUuid: "j-1")
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/installations/2012/analytics/exports/j-1/")
        XCTAssertEqual(st.rowCount, 4)
        XCTAssertEqual(st.error, "")
    }

    func testExportDownloadReturnsRawBytesWithSig() async throws {
        CaptureMock.reply = "a,b\n1,2\n"
        let data = try await client().forInstallation(id: 2012).exports.download(jobUuid: "j-1", sig: "z")
        XCTAssertEqual(CaptureMock.lastMethod, "GET")
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/installations/2012/analytics/exports/j-1/download/?sig=z")
        XCTAssertEqual(data, Data("a,b\n1,2\n".utf8))
    }

    func testRevokeTokenPosts() async throws {
        CaptureMock.reply = "{}"
        try await client().revokeToken()
        XCTAssertEqual(CaptureMock.lastMethod, "POST")
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/auth/token/revoke")
    }

    func testSetHotspotsPatchesFullReplacement() async throws {
        CaptureMock.reply = #"{"uuid":"m-1","measurement_point_id":5,"point_sequence":1,"data":{},"status":"good","notes":"","created_at":"2026-01-01T00:00:00Z"}"#
        let m = try await client().forInstallation(id: 2012).measurements.setHotspots(
            measurementUuid: "m-1", hotClusters: [HotCluster(cxPct: 10, cyPct: 20, maxTempC: 80.5, deltaTC: 12, severity: 2, source: "manual")])
        XCTAssertEqual(CaptureMock.lastMethod, "PATCH")
        XCTAssertEqual(CaptureMock.lastPath, "https://x.test/api/installations/2012/measurements/m-1/hotspots/")
        let hc = try XCTUnwrap(CaptureMock.lastJSON?["hot_clusters"] as? [[String: Any]])
        XCTAssertEqual(hc.first?["cx_pct"] as? Double, 10)
        XCTAssertEqual(hc.first?["severity"] as? Int, 2)
        XCTAssertEqual(m.uuid, "m-1")
    }
}
