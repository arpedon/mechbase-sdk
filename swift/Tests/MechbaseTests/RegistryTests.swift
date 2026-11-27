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

    func testMeasurementPointImageUrlsDecode() throws {
        let json = #"""
        {"uuid":"p-1","point_id":1,"name":"DE","asset_id":1,"transducer_type":"VB",
         "measurement_unit_code":"mm/s","location":"","status":1,
         "image_urls":["https://app.mechbase.io/media/a.jpg","https://app.mechbase.io/media/b.png"]}
        """#
        let p = try JSONDecoder().decode(MeasurementPoint.self, from: Data(json.utf8))
        XCTAssertEqual(p.imageUrls, ["https://app.mechbase.io/media/a.jpg", "https://app.mechbase.io/media/b.png"])
    }

    func testAssetImageUrlsDecodeAndDefaultEmpty() throws {
        let with = #"{"uuid":"a-1","asset_id":1,"name":"Pump","status":1,"image_urls":["https://x/a.jpg"]}"#
        let without = #"{"uuid":"a-1","asset_id":1,"name":"Pump","status":1}"#
        XCTAssertEqual(try JSONDecoder().decode(Asset.self, from: Data(with.utf8)).imageUrls, ["https://x/a.jpg"])
        XCTAssertEqual(try JSONDecoder().decode(Asset.self, from: Data(without.utf8)).imageUrls, [])
    }

    // MARK: asset types, guest view, checklist

    private func body(_ r: URLRequest) -> [String: Any] {
        var data = r.httpBody ?? Data()
        if let st = r.httpBodyStream {
            st.open(); defer { st.close() }
            var buf = [UInt8](repeating: 0, count: 4096)
            while st.hasBytesAvailable { let n = st.read(&buf, maxLength: buf.count); if n <= 0 { break }; data.append(buf, count: n) }
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    func testAssetTypeOmittedNullCode() async throws {
        var bodies: [[String: Any]] = []
        MockURLProtocol.handler = { req in
            XCTAssertEqual(req.url?.path, "/api/installations/2012/assets/1")
            XCTAssertEqual(req.httpMethod, "PATCH")
            bodies.append(self.body(req))
            return (200, self.json(#"{"uuid":"a","asset_id":1,"name":"P","status":1,"asset_type":"QB-STD"}"#))
        }
        let assets = client.forInstallation(id: 2012).assets
        let a = try await assets.update(id: 1, AssetInput(name: "P"))
        XCTAssertEqual(a.assetType, "QB-STD")
        _ = try await assets.update(id: 1, AssetInput(assetType: .some(nil)))
        _ = try await assets.update(id: 1, AssetInput(assetType: "QB-STD"))
        XCTAssertEqual(bodies[0].keys.sorted(), ["name"])
        XCTAssertEqual(bodies[1].count, 1)
        XCTAssertTrue(bodies[1]["asset_type"] is NSNull)
        XCTAssertEqual(bodies[2]["asset_type"] as? String, "QB-STD")
    }

    func testZoneGuestViewAndEnsureChecklist() async throws {
        MockURLProtocol.handler = { req in
            if req.url?.path.hasSuffix("/zones/3") == true {
                XCTAssertEqual(req.httpMethod, "PATCH")
                XCTAssertEqual(self.body(req)["guest_view"] as? Bool, true)
                return (200, self.json(#"{"uuid":"z","zone_id":3,"name":"Z","guest_view":true}"#))
            }
            XCTAssertEqual(req.url?.path, "/api/installations/2012/assets/1/checklist")
            XCTAssertEqual(req.httpMethod, "POST")
            return (200, self.json(#"{"route_uuid":"r","created":true}"#))
        }
        let inst = client.forInstallation(id: 2012)
        let z = try await inst.zones.update(id: 3, ZoneInput(guestView: true))
        XCTAssertTrue(z.guestView)
        let c = try await inst.assets.ensureChecklist(assetId: 1)
        XCTAssertEqual(c.routeUuid, "r")
        XCTAssertTrue(c.created)
        let old = try JSONDecoder().decode(Zone.self, from: Data(#"{"uuid":"z","name":"Z"}"#.utf8))
        XCTAssertFalse(old.guestView)
    }

    func testAssetTypesPaths() async throws {
        var seen: [String] = []
        MockURLProtocol.handler = { req in
            seen.append("\(req.httpMethod!) \(req.url!.path)")
            switch (req.httpMethod!, req.url!.path) {
            case ("GET", "/api/installations/2012/asset-types"):
                return (200, self.json(#"[{"uuid":"t","code":"QB-STD","name":"QB","checklist":[{"label":"x"}],"asset_count":2,"document_count":1}]"#))
            case ("DELETE", "/api/installations/2012/asset-types/QB-STD"):
                return (200, self.json(#"{"deleted":true,"uuid":"t"}"#))
            case ("GET", _) where req.url!.path.hasSuffix("/documents"):
                return (200, self.json(#"[{"uuid":"d","name":"m.pdf","kind":"manual","url":"u","created_at":"c"}]"#))
            case ("POST", _):
                return (201, self.json(#"{"uuid":"d","name":"m.pdf","kind":"manual","url":"u","created_at":"c"}"#))
            case ("DELETE", _):
                return (204, Data())
            default:
                if req.httpMethod != "GET" { XCTAssertEqual(self.body(req)["name"] as? String, "QB") }
                return (200, self.json(#"{"uuid":"t","code":"QB-STD","name":"QB"}"#))
            }
        }
        let at = client.forInstallation(id: 2012).assetTypes
        let list = try await at.list()
        XCTAssertEqual(list[0].documentCount, 1)
        XCTAssertEqual(list[0].checklist.count, 1)
        _ = try await at.upsert(AssetTypeInput(code: "QB-STD", name: "QB"))
        _ = try await at.update(code: "QB-STD", AssetTypeInput(name: "QB"))
        _ = try await at.get(code: "QB-STD")
        let del = try await at.delete(code: "QB-STD")
        XCTAssertTrue(del.deleted)
        let docs = try await at.documents(code: "QB-STD")
        XCTAssertEqual(docs.count, 1)
        _ = try await at.addDocument(code: "QB-STD", file: Data("%PDF".utf8), kind: "manual")
        try await at.deleteDocument(code: "QB-STD", uuid: "11111111-1111-1111-1111-111111111111")
        XCTAssertEqual(seen, ["GET /api/installations/2012/asset-types", "PUT /api/installations/2012/asset-types",
            "PATCH /api/installations/2012/asset-types/QB-STD", "GET /api/installations/2012/asset-types/QB-STD",
            "DELETE /api/installations/2012/asset-types/QB-STD", "GET /api/installations/2012/asset-types/QB-STD/documents",
            "POST /api/installations/2012/asset-types/QB-STD/documents",
            "DELETE /api/installations/2012/asset-types/QB-STD/documents/11111111-1111-1111-1111-111111111111"])
    }
}
