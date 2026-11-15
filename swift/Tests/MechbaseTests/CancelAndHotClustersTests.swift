import XCTest
@testable import Mechbase

/// `Execution.cancel` hits the cancel endpoint; `measurements.create(hotClusters:)`
/// sends hot_clusters top-level (the server strips it from `data`), and omits it
/// when nil so the server still runs its own detection.
final class CancelAndHotClustersTests: XCTestCase {
    private func client() -> MechbaseClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [CaptureMock.self]
        return MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
    }

    func testCancelPostsToCancelEndpoint() async throws {
        CaptureMock.reply = #"{"uuid":"exec-1","route_uuid":"route-1","status":"cancelled","started_at":"2026-11-15T08:30:00Z","completed_at":null,"session_id":"sess-1"}"#
        let result = try await client().forInstallation(id: 2012).routes.execution(uuid: "exec-1").cancel()
        XCTAssertEqual(result.status, "cancelled")
        XCTAssertEqual(CaptureMock.lastMethod, "POST")
        XCTAssertTrue(CaptureMock.lastPath?.hasSuffix("/installations/2012/executions/exec-1/cancel") ?? false)
    }

    func testLegacyRedirectsDecodesItems() async throws {
        CaptureMock.reply = #"{"items":[{"legacy_url":"https://mechbase.arpedon.com/measurementpoint/0b7c6f2e-1d2a-4b4c-9f00-1a2b3c4d5e6f/","mp_uuid":"9a8b7c6d-1d2a-4b4c-9f00-1a2b3c4d5e6f","mp_path":"/2012/assets/3/measurementpoints/5/","installation_id":2012,"asset_id":3,"point_id":5}],"total":1}"#
        let items = try await client().forInstallation(id: 2012).legacyRedirects()
        XCTAssertEqual(items.first?.pointId, 5)
        XCTAssertTrue(CaptureMock.lastPath?.hasSuffix("/installations/2012/legacy-redirects") ?? false)
    }

    func testHotClustersSentTopLevelAndOmittedWhenNil() async throws {
        CaptureMock.reply = #"{"uuid":"m1","measurement_point_id":5,"point_sequence":1,"data":{"value":40},"status":"good","notes":"","created_at":"2026-01-01T00:00:00Z"}"#
        let scope = client().forInstallation(id: 2012)

        _ = try await scope.measurements.create(pointId: 5, data: .object(["value": .double(40)]), hotClusters: .array([]))
        var body = try XCTUnwrap(CaptureMock.lastJSON)
        XCTAssertEqual((body["hot_clusters"] as? [Any])?.count, 0, "an analyst-cleared [] must reach the server")
        XCTAssertNil((body["data"] as? [String: Any])?["hot_clusters"])

        _ = try await scope.measurements.create(pointId: 5, data: .object(["value": .double(40)]))
        body = try XCTUnwrap(CaptureMock.lastJSON)
        XCTAssertFalse(body.keys.contains("hot_clusters"), "nil must be omitted so the server runs detection")
    }
}

final class CaptureMock: URLProtocol {
    nonisolated(unsafe) static var reply = "{}"
    nonisolated(unsafe) static var lastMethod: String?
    nonisolated(unsafe) static var lastPath: String?
    nonisolated(unsafe) static var lastJSON: [String: Any]?
    override class func canInit(with r: URLRequest) -> Bool { true }
    override class func canonicalRequest(for r: URLRequest) -> URLRequest { r }
    override func startLoading() {
        CaptureMock.lastMethod = request.httpMethod
        CaptureMock.lastPath = request.url?.absoluteString
        let data = request.httpBody ?? request.httpBodyStream.map(Self.read) ?? Data()
        CaptureMock.lastJSON = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        let resp = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: "HTTP/1.1",
                                   headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(CaptureMock.reply.utf8)); client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
    private static func read(_ s: InputStream) -> Data {
        s.open(); defer { s.close() }
        var out = Data(); var buf = [UInt8](repeating: 0, count: 4096)
        while s.hasBytesAvailable { let n = s.read(&buf, maxLength: buf.count); if n <= 0 { break }; out.append(buf, count: n) }
        return out
    }
}
