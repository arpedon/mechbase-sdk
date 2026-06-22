import XCTest
@testable import Mechbase

/// `Routes.start` body shape: offline-first clients pass a client-minted `uuid`
/// (and the real field `startedAt`) so a queued start can be pushed and the
/// server upserts on it; bare callers keep the legacy empty POST. See issue #11.
final class RouteStartTests: XCTestCase {
    override func tearDown() {
        RouteStartMock.lastBody = nil
        RouteStartMock.lastPath = nil
        RouteStartMock.lastMethod = nil
        super.tearDown()
    }

    private func makeClient() -> MechbaseClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [RouteStartMock.self]
        return MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
    }

    func testStartWithClientUuidAndStartedAtSendsThemInBody() async throws {
        let client = makeClient()
        let exec = try await client.forInstallation(id: 2012).routes.start(
            routeUUID: "route-1", uuid: "exec-1", startedAt: Date(timeIntervalSince1970: 1_750_000_000))

        XCTAssertEqual(exec.uuid, "exec-1")
        XCTAssertEqual(RouteStartMock.lastMethod, "POST")
        XCTAssertTrue(RouteStartMock.lastPath?.hasSuffix("/routes/route-1/executions") ?? false)
        let body = RouteStartMock.lastBody.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        XCTAssertEqual(body?["uuid"] as? String, "exec-1")
        XCTAssertNotNil(body?["started_at"], "body should carry started_at")
    }

    func testStartWithoutArgsPostsAnEmptyBody() async throws {
        let client = makeClient()
        _ = try await client.forInstallation(id: 2012).routes.start(routeUUID: "route-1")

        XCTAssertEqual(RouteStartMock.lastMethod, "POST")
        XCTAssertTrue(RouteStartMock.lastPath?.hasSuffix("/routes/route-1/executions") ?? false)
        XCTAssertNil(RouteStartMock.lastBody, "bare start is the legacy empty POST (server mints the uuid)")
    }
}

/// Captures the outgoing request (method, path, body) and returns a valid
/// `RouteExecution`. The body of a `URLRequest.httpBody` arrives as
/// `httpBodyStream` once URLSession hands it to a URLProtocol, so drain that.
final class RouteStartMock: URLProtocol {
    nonisolated(unsafe) static var lastBody: Data?
    nonisolated(unsafe) static var lastPath: String?
    nonisolated(unsafe) static var lastMethod: String?

    override class func canInit(with r: URLRequest) -> Bool { true }
    override class func canonicalRequest(for r: URLRequest) -> URLRequest { r }

    override func startLoading() {
        RouteStartMock.lastMethod = request.httpMethod
        RouteStartMock.lastPath = request.url?.path
        if let stream = request.httpBodyStream {
            stream.open()
            var data = Data()
            let size = 4096
            let buf = UnsafeMutablePointer<UInt8>.allocate(capacity: size)
            defer { buf.deallocate() }
            while stream.hasBytesAvailable {
                let read = stream.read(buf, maxLength: size)
                if read <= 0 { break }
                data.append(buf, count: read)
            }
            stream.close()
            RouteStartMock.lastBody = data
        } else {
            RouteStartMock.lastBody = request.httpBody
        }
        let respBody = #"{"uuid":"exec-1","route_uuid":"route-1","status":"in_progress","started_at":"2026-06-22T08:30:00Z","completed_at":null,"session_id":"sess-1"}"#
        let resp = HTTPURLResponse(url: request.url!, statusCode: 201, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(respBody.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
