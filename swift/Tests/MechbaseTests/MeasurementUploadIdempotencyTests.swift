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

    /// mechbase-web#407: the client uuid travels as a form field so a retry dedupes.
    func testAddFileSendsClientUuid() async throws {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [UploadIdemMock.self]
        let client = MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
        let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("a.dr")
        try Data([0, 1]).write(to: tmp)
        UploadIdemMock.responseBody = #"{"uuid":"file-uuid-1","name":"a.dr","kind":"attachment","file_url":"https://x/a.dr","created_at":"2026-01-01T00:00:00Z"}"#
        defer { UploadIdemMock.responseBody = nil }
        _ = try await client.forInstallation(id: 2012).measurements.addFile(
            measurementUUID: "m1", fileURL: tmp, uuid: "file-uuid-1")
        XCTAssertTrue(UploadIdemMock.lastPath?.hasSuffix("/measurements/m1/files/") ?? false)
        XCTAssertTrue(UploadIdemMock.lastBody?.contains("name=\"uuid\"\r\n\r\nfile-uuid-1") ?? false)
    }
}

final class UploadIdemMock: URLProtocol {
    nonisolated(unsafe) static var lastIdem: String?
    nonisolated(unsafe) static var lastPath: String?
    nonisolated(unsafe) static var lastBody: String?
    nonisolated(unsafe) static var responseBody: String?
    override class func canInit(with r: URLRequest) -> Bool { true }
    override class func canonicalRequest(for r: URLRequest) -> URLRequest { r }
    override func startLoading() {
        UploadIdemMock.lastIdem = request.value(forHTTPHeaderField: "X-Idempotency-Key")
        UploadIdemMock.lastPath = request.url?.absoluteString
        UploadIdemMock.lastBody = Self.bodyString(request)
        let body = UploadIdemMock.responseBody ?? #"{"uuid":"m1","measurement_point_id":5,"point_sequence":1,"data":{"rms":1.2},"status":"good","notes":"","created_at":"2026-01-01T00:00:00Z"}"#
        let resp = HTTPURLResponse(url: request.url!, statusCode: 201, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8)); client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}

    /// URLSession hands the protocol a stream, not `httpBody`.
    static func bodyString(_ r: URLRequest) -> String? {
        if let b = r.httpBody { return String(decoding: b, as: UTF8.self) }
        guard let s = r.httpBodyStream else { return nil }
        s.open(); defer { s.close() }
        var data = Data(); var buf = [UInt8](repeating: 0, count: 4096)
        while s.hasBytesAvailable { let n = s.read(&buf, maxLength: buf.count); if n <= 0 { break }; data.append(buf, count: n) }
        return String(decoding: data, as: UTF8.self)
    }
}
