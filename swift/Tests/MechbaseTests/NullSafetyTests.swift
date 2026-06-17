import XCTest
@testable import Mechbase

/// Hardening tests for issue #2: the Swift SDK must survive a server response
/// that contains an explicit JSON `null` on a property our models declare
/// non-nullable, instead of throwing at decode and taking down the calling
/// screen.
///
/// Mirrors the Kotlin NullSafetyTest case-for-case. Where the Kotlin SDK
/// uses the `coerceInputValues = true` global flag, the Swift SDK has
/// already had the per-field `(try? decode(...)) ?? ""` pattern applied
/// consistently — the only field changes here are widening to optional
/// (`MeasurementPoint.transducerType/measurementUnitCode/location` gain
/// the pattern; `Measurement.pointSequence` widens to `Int?`).
@MainActor
final class NullSafetyTests: XCTestCase {
    var client: MechbaseClient!

    override func setUp() {
        super.setUp()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        client = MechbaseClient(
            token: "tok",
            baseURL: URL(string: "https://example.test")!,
            session: URLSession(configuration: config)
        )
    }

    override func tearDown() {
        MockURLProtocol.handler = nil
        client = nil
        super.tearDown()
    }

    private func json(_ s: String) -> Data { s.data(using: .utf8)! }

    /// A: `Route.description: null` falls back to "" — was the exact
    /// production crash on installations 2012/2013 (issue #164 server,
    /// #2 client).
    func testRouteDescriptionNullFallsBackToEmpty() async throws {
        MockURLProtocol.handler = { _ in
            (200, self.json(#"""
            {"items":[{"uuid":"r-1","name":"Daily","description":null}],
             "total":1,"limit":50,"offset":0}
            """#))
        }
        let r = try await client.forInstallation(id: 2012).routes.list()
        XCTAssertEqual(r.count, 1)
        XCTAssertEqual(r[0].description, "")
    }

    /// A: defaulted `notes` on `ItemResponse` survives `null`.
    func testItemResponseNotesNullFallsBackToEmpty() async throws {
        var calls = 0
        MockURLProtocol.handler = { req in
            calls += 1
            if req.url?.path == "/api/installations/2012/routes/r-uuid/executions" {
                return (201, self.json(#"""
                {"uuid":"exec-1","route_uuid":"r-uuid","status":"in_progress",
                 "started_at":"t","completed_at":null,"session_id":"sess-1"}
                """#))
            }
            if req.url?.path == "/api/installations/2012/executions/exec-1/responses" {
                return (201, self.json(#"""
                {"uuid":"resp-1","route_item_uuid":"item-1","data":{},
                 "notes":null,"status":1,"created_at":"t"}
                """#))
            }
            return (404, self.json(#"{"detail":"unexpected"}"#))
        }
        let exec = try await client.forInstallation(id: 2012).routes.start(routeUUID: "r-uuid")
        let resp = try await exec.respond(routeItemUUID: "item-1", data: ["passed": true])
        XCTAssertEqual(resp.notes, "")
        XCTAssertEqual(calls, 2)
    }

    /// A: defaulted `notes` on `Measurement` survives `null`.
    func testMeasurementNotesNullFallsBackToEmpty() async throws {
        MockURLProtocol.handler = { _ in
            (201, self.json(#"""
            {"uuid":"m-1","measurement_point_id":1,"point_sequence":1,
             "data":{},"status":"good","notes":null,"created_at":"t","file_url":null}
            """#))
        }
        let m = try await client.forInstallation(id: 2012)
            .measurements.create(pointId: 1, data: ["rms": 2.3])
        XCTAssertEqual(m.notes, "")
    }

    /// B: `Measurement.pointSequence` widens to `Int?` — the backing
    /// column is genuinely `null=True` on the server. `decode(Int.self)`
    /// would throw on null; `decodeIfPresent` decodes to nil.
    func testMeasurementPointSequenceNullDecodes() async throws {
        MockURLProtocol.handler = { _ in
            (201, self.json(#"""
            {"uuid":"m-1","measurement_point_id":1,"point_sequence":null,
             "data":{"rms":2.3},"status":"good","notes":"","created_at":"t","file_url":null}
            """#))
        }
        let m = try await client.forInstallation(id: 2012)
            .measurements.create(pointId: 1, data: ["rms": 2.3])
        XCTAssertNil(m.pointSequence)
        XCTAssertEqual(m.status, "good")
    }

    /// B: `MeasurementPoint.transducerType/measurementUnitCode/location`
    /// all-null decodes to empty strings (per-field pattern application).
    func testMeasurementPointOptionalMetadataAllNullDecodes() async throws {
        // The create() endpoint echoes the created point. We use a
        // dedicated handler that returns a server response with the three
        // optional fields explicitly null.
        MockURLProtocol.handler = { _ in
            (201, self.json(#"""
            {"uuid":"p-1","point_id":1,"name":"Drive End","asset_id":100,
             "transducer_type":null,"measurement_unit_code":null,"location":null,
             "status":1,"external_id":"P-1-DE"}
            """#))
        }
        let p = try await client.forInstallation(id: 2012)
            .measurementPoints.create(PointInput(name: "Drive End", externalId: "P-1-DE"))
        XCTAssertEqual(p.transducerType, "")
        XCTAssertEqual(p.measurementUnitCode, "")
        XCTAssertEqual(p.location, "")
    }

    /// Regression guard: a fully populated response still decodes the same
    /// way after the widening.
    func testFullyPopulatedResponseStillDecodes() async throws {
        MockURLProtocol.handler = { _ in
            (201, self.json(#"""
            {"uuid":"m-1","measurement_point_id":1,"point_sequence":7,
             "data":{"rms":2.3},"status":"good","notes":"manual",
             "created_at":"t","file_url":null}
            """#))
        }
        let m = try await client.forInstallation(id: 2012)
            .measurements.create(pointId: 1, data: ["rms": 2.3])
        XCTAssertEqual(m.pointSequence, 7)
        XCTAssertEqual(m.notes, "manual")
    }
}
