import XCTest
@testable import Mechbase

final class MeasurementUploadIdempotencyTests: XCTestCase {
    func testMultipartCreateSendsIdempotencyKey() async throws {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [UploadIdemMock.self]
        let client = MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("c.dr")
        try Data([0, 1, 2, 3]).write(to: tmp)
        _ = try await client.forInstallation(id: 2012).measurements.create(
            pointId: 5, data: .object(["rms": .double(1.2)]), notes: "",
            fileURL: tmp, mimeType: "application/octet-stream", idempotencyKey: "idem-123")
        XCTAssertEqual(UploadIdemMock.lastIdem, "idem-123")
        XCTAssertTrue(UploadIdemMock.lastPath?.hasSuffix("/measurements/upload/") ?? false)
    }
}

final class UploadIdemMock: URLProtocol {
    nonisolated(unsafe) static var lastIdem: String?
    nonisolated(unsafe) static var lastPath: String?
    override class func canInit(with r: URLRequest) -> Bool { true }
    override class func canonicalRequest(for r: URLRequest) -> URLRequest { r }
    override func startLoading() {
        UploadIdemMock.lastIdem = request.value(forHTTPHeaderField: "X-Idempotency-Key")
        UploadIdemMock.lastPath = request.url?.absoluteString
        let body = #"{"uuid":"m1","measurement_point_id":5,"point_sequence":1,"data":{"rms":1.2},"status":"good","notes":"","created_at":"2026-01-01T00:00:00Z"}"#
        let resp = HTTPURLResponse(url: request.url!, statusCode: 201, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8)); client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
