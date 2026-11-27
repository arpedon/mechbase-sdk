import XCTest
@testable import Mechbase

/// URLProtocol stub for the parity tests: replies with `status`/`reply`/`headers` and records the request.
final class ParityMock: URLProtocol {
    nonisolated(unsafe) static var status = 200
    nonisolated(unsafe) static var reply = "{}"
    nonisolated(unsafe) static var headers: [String: String] = [:]
    nonisolated(unsafe) static var request: URLRequest?
    nonisolated(unsafe) static var body = Data()

    static func reset(status: Int = 200, reply: String = "{}", headers: [String: String] = [:]) {
        self.status = status; self.reply = reply; self.headers = headers; request = nil; body = Data()
    }

    override class func canInit(with r: URLRequest) -> Bool { true }
    override class func canonicalRequest(for r: URLRequest) -> URLRequest { r }
    override func startLoading() {
        ParityMock.request = request
        ParityMock.body = request.httpBody ?? request.httpBodyStream.map(Self.read) ?? Data()
        let resp = HTTPURLResponse(url: request.url!, statusCode: ParityMock.status, httpVersion: "HTTP/1.1",
                                   headerFields: ["Content-Type": "application/json"].merging(ParityMock.headers) { _, b in b })!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(ParityMock.reply.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
    private static func read(_ s: InputStream) -> Data {
        s.open(); defer { s.close() }
        var out = Data(); var buf = [UInt8](repeating: 0, count: 4096)
        while s.hasBytesAvailable { let n = s.read(&buf, maxLength: buf.count); if n <= 0 { break }; out.append(buf, count: n) }
        return out
    }
}

/// Base for the parity tests: a client on the mock, and accessors for what was sent.
class ParityTestCase: XCTestCase {
    let base = "https://x.test/api/installations/7"
    let u1 = "6f1c0000-0000-4000-8000-000000000001"
    let u2 = "6f1c0000-0000-4000-8000-000000000002"
    let u3 = "6f1c0000-0000-4000-8000-000000000003"

    var client: MechbaseClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [ParityMock.self]
        return MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
    }
    var inst: Installation { client.forInstallation(id: 7) }

    override func setUp() { super.setUp(); ParityMock.reset() }

    /// Reply with the generated fixture for `schema` (`nulls`: nullable null, defaults absent).
    func reply(_ schema: String, nulls: Bool = false, status: Int = 200, list: Bool = false) {
        let one = (nulls ? Fixture.nulls : Fixture.full)[schema]!
        ParityMock.reset(status: status, reply: list ? "[\(one)]" : one)
    }

    var method: String? { ParityMock.request?.httpMethod }
    var url: String? { ParityMock.request?.url?.absoluteString }
    func header(_ name: String) -> String? { ParityMock.request?.value(forHTTPHeaderField: name) }
    var json: [String: Any] { (try? JSONSerialization.jsonObject(with: ParityMock.body)) as? [String: Any] ?? [:] }
    var bodyText: String { String(decoding: ParityMock.body, as: UTF8.self) }

    /// The value of multipart field `name`, or nil.
    func formField(_ name: String) -> String? {
        let marker = "name=\"\(name)\"\r\n\r\n"
        guard let r = bodyText.range(of: marker) else { return nil }
        let rest = bodyText[r.upperBound...]
        return String(rest[..<(rest.range(of: "\r\n")?.lowerBound ?? rest.endIndex)])
    }

    func expectError(_ body: () async throws -> Void, file: StaticString = #filePath, line: UInt = #line,
                     _ match: (MechbaseError) -> Bool) async {
        do { try await body(); XCTFail("expected an error", file: file, line: line) } catch let e as MechbaseError {
            XCTAssertTrue(match(e), "wrong error: \(e)", file: file, line: line)
        } catch { XCTFail("wrong error type: \(error)", file: file, line: line) }
    }
}
