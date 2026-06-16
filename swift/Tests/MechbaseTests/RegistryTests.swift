import XCTest
@testable import Mechbase

@MainActor
final class RegistryTests: XCTestCase {
    var client: MechbaseClient!

    override func setUp() {
        super.setUp()
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [MockURLProtocol.self]
        client = MechbaseClient(token: "tok", baseURL: URL(string: "https://example.test")!,
                                session: URLSession(configuration: config))
    }
    override func tearDown() { MockURLProtocol.handler = nil; client = nil; super.tearDown() }
    private func json(_ s: String) -> Data { s.data(using: .utf8)! }

    func testCreateAsset() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/installations/2012/assets")
            XCTAssertEqual(req.httpMethod, "POST")
            return (201, self.json("""
            {"uuid":"a-1","asset_id":7,"name":"Pump 7","section_id":3,"zone_id":2,
             "machine_class":"II","equipment_type":"pump","status":1,"external_id":"P-7"}
            """))
        }
        let a = try await client.forInstallation(id: 2012).assets.create(
            AssetInput(name: "Pump 7", externalId: "P-7"))
        XCTAssertEqual(a.assetId, 7)
        XCTAssertEqual(a.equipmentType, "pump")
    }

    func testCreateZone() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/installations/2012/zones")
            XCTAssertEqual(req.httpMethod, "POST")
            return (201, self.json("""
            {"uuid":"z-1","zone_id":9,"name":"Zone 9","section_id":3,"external_id":"Z-9"}
            """))
        }
        let z = try await client.forInstallation(id: 2012).zones.create(
            ZoneInput(name: "Zone 9", externalId: "Z-9", sectionExternalId: "S-1"))
        XCTAssertEqual(z.zoneId, 9)
    }

    func testCreateBatch() async throws {
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.absoluteString, "https://example.test/api/installations/2012/measurements/batch/")
            XCTAssertEqual(req.httpMethod, "POST")
            return (200, self.json("""
            {"created":1,"duplicates":0,"errors":0,"results":[
              {"index":0,"status":"created","measurement_point_id":1,"point_sequence":5,
               "uuid":"m-1","external_id":"E-0","detail":null}]}
            """))
        }
        let res = try await client.forInstallation(id: 2012).measurements.createBatch([
            MeasurementInput(measurementPointId: 1, data: ["rms": 2.3], externalId: "E-0"),
        ])
        XCTAssertEqual(res.created, 1)
        XCTAssertEqual(res.results.first?.status, "created")
    }

    func testIterForPoint() async throws {
        var page = 0
        MockURLProtocol.handler = { req in
            page += 1
            if page == 1 {
                XCTAssertTrue(req.url?.query?.contains("cursor=") ?? false, "first request must send cursor= to opt into cursor mode")
                return (200, self.json("""
                {"items":[{"uuid":"m-1","measurement_point_id":42,"point_sequence":1,
                 "data":{},"status":"good","notes":"","created_at":"t1"}],"next_cursor":"CUR2"}
                """))
            }
            XCTAssertTrue(req.url?.query?.contains("cursor=CUR2") ?? false, "second request must carry cursor=CUR2")
            return (200, self.json("""
            {"items":[{"uuid":"m-2","measurement_point_id":42,"point_sequence":2,
             "data":{},"status":"good","notes":"","created_at":"t2"}],"next_cursor":null}
            """))
        }
        var got: [String] = []
        for try await m in client.forInstallation(id: 2012).measurements.iterForPoint(pointId: 42, pageSize: 1) {
            got.append(m.uuid)
        }
        XCTAssertEqual(got, ["m-1", "m-2"])
    }
}
