import XCTest
@testable import Mechbase

/// URLProtocol stub: each test sets `MockURLProtocol.handler` to a closure
/// that returns the (status, body) for the inbound request.
final class MockURLProtocol: URLProtocol {
    nonisolated(unsafe) static var handler: ((URLRequest) -> (Int, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        guard let handler = MockURLProtocol.handler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        let (status, data) = handler(request)
        let resp = HTTPURLResponse(
            url: request.url!,
            statusCode: status,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": "application/json"]
        )!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

@MainActor
final class MechbaseTests: XCTestCase {
    var client: MechbaseClient!

    override func setUp() {
        super.setUp()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        let session = URLSession(configuration: config)
        client = MechbaseClient(
            token: "tok",
            baseURL: URL(string: "https://example.test")!,
            session: session
        )
    }

    override func tearDown() {
        MockURLProtocol.handler = nil
        client = nil
        super.tearDown()
    }

    private func json(_ s: String) -> Data { s.data(using: .utf8)! }

    func testMe() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/me")
            XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer tok")
            let body = """
            {"user":{"id":1,"username":"u","full_name":"U U","email":"u@u"},
             "installations":[{"installation_id":2012,"name":"Plant"}],
             "current_installation_id":2012}
            """
            return (200, self.json(body))
        }
        let me = try await client.me()
        XCTAssertEqual(me.user.username, "u")
        XCTAssertEqual(me.currentInstallationId, 2012)
        XCTAssertEqual(me.installations.first?.name, "Plant")
    }

    func testListAssets() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/installations/2012/assets")
            let body = """
            {"items":[{"uuid":"00000000-0000-0000-0000-000000000001","asset_id":1,
            "name":"Pump 1","zone_id":1,"machine_class":"II","status":1}],
            "total":1,"limit":50,"offset":0}
            """
            return (200, self.json(body))
        }
        let assets = try await client.forInstallation(id: 2012).assets.list()
        XCTAssertEqual(assets.count, 1)
        XCTAssertEqual(assets[0].name, "Pump 1")
    }

    func testCreateMeasurement() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.absoluteString, "https://example.test/api/installations/2012/measurements/")
            XCTAssertEqual(req.httpMethod, "POST")
            let body = """
            {"uuid":"00000000-0000-0000-0000-000000000002","measurement_point_id":1,
            "point_sequence":5,"data":{"rms":2.3},"status":"good","notes":"",
            "created_at":"2026-04-08T10:00:00Z","file_url":null}
            """
            return (201, self.json(body))
        }
        let m = try await client.forInstallation(id: 2012)
            .measurements.create(pointId: 1, data: ["rms": 2.3])
        XCTAssertEqual(m.pointSequence, 5)
        XCTAssertEqual(m.status, "good")
    }

    func testAuthErrorRaises() async {
        MockURLProtocol.handler = { _ in (401, self.json(#"{"detail":"nope"}"#)) }
        do {
            _ = try await client.me()
            XCTFail("expected error")
        } catch let e as MechbaseError {
            if case .auth = e { /* ok */ } else { XCTFail("wrong case: \(e)") }
        } catch {
            XCTFail("wrong type: \(error)")
        }
    }

    func testStartExecutionAndRespond() async throws {
        var calls = 0
        MockURLProtocol.handler = { req in
            calls += 1
            if req.url?.path == "/api/installations/2012/routes/r-uuid/executions" {
                let body = """
                {"uuid":"exec-uuid","route_uuid":"r-uuid","status":"in_progress",
                "started_at":"2026-04-08T10:00:00Z","completed_at":null,"session_id":"sess-uuid"}
                """
                return (201, self.json(body))
            }
            if req.url?.path == "/api/installations/2012/executions/exec-uuid/responses" {
                let body = """
                {"uuid":"resp-uuid","route_item_uuid":"item-uuid","data":{"passed":true},
                "notes":"","status":1,"created_at":"2026-04-08T10:00:01Z"}
                """
                return (201, self.json(body))
            }
            return (404, self.json(#"{"detail":"unexpected"}"#))
        }
        let exec = try await client.forInstallation(id: 2012).routes.start(routeUUID: "r-uuid")
        XCTAssertEqual(exec.uuid, "exec-uuid")
        let resp = try await exec.respond(routeItemUUID: "item-uuid", data: ["passed": true])
        XCTAssertEqual(resp.status, 1)
        XCTAssertEqual(calls, 2)
    }
}
