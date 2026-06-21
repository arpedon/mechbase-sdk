import XCTest
@testable import Mechbase

final class RouteDetailTests: XCTestCase {
    func testRouteDetailDecodesWithNullSectionAndItems() throws {
        let json = """
        {"uuid":"r1","name":"Monthly Check","description":"",
         "section":{"section_id":null,"name":"Power House"},
         "items":[
           {"uuid":"i1","check_id":1,"label":"Auto-start","item_type":"pass_fail","asset_id":5,"zone_id":9,"zone_name":"Power House","measurement_point_id":null,"config":{}},
           {"uuid":"i2","check_id":2,"label":"Battery","item_type":"numerical","asset_id":5,"zone_id":9,"zone_name":"Power House","measurement_point_id":7,"config":{"unit":"V"}}
         ]}
        """
        let d = try JSONDecoder().decode(RouteDetail.self, from: Data(json.utf8))
        XCTAssertEqual(d.uuid, "r1")
        XCTAssertEqual(d.section?.sectionId, nil)
        XCTAssertEqual(d.section?.name, "Power House")
        XCTAssertEqual(d.items.count, 2)
        XCTAssertEqual(d.items[0].itemType, "pass_fail")
        XCTAssertEqual(d.items[1].measurementPointId, 7)
        // Point-screen fields default cleanly when the payload omits them.
        XCTAssertEqual(d.items[0].instructions, [])
        XCTAssertNil(d.items[0].referenceImageUrl)
        XCTAssertNil(d.items[0].limit)
    }

    func testRouteItemDecodesPointScreenFields() throws {
        let json = """
        {"uuid":"r2","name":"Point screen","description":"","section":null,
         "items":[
           {"uuid":"i1","check_id":1,"label":"Scan windings","item_type":"measurement",
            "asset_id":5,"zone_id":9,"zone_name":"Hall","measurement_point_id":7,"config":{},
            "instructions":["Run 30 min","Frame at 1 m"],
            "reference_image_url":"https://app.mechbase.io/media/assets/ref.jpg",
            "limit":{"minor":4.5,"major":7.1,"direction":"high","unit":"mm/s"}}
         ]}
        """
        let d = try JSONDecoder().decode(RouteDetail.self, from: Data(json.utf8))
        let item = d.items[0]
        XCTAssertEqual(item.instructions, ["Run 30 min", "Frame at 1 m"])
        XCTAssertEqual(item.referenceImageUrl, "https://app.mechbase.io/media/assets/ref.jpg")
        XCTAssertEqual(item.limit?.minor, 4.5)
        XCTAssertEqual(item.limit?.major, 7.1)
        XCTAssertEqual(item.limit?.direction, "high")
        XCTAssertEqual(item.limit?.unit, "mm/s")
    }

    func testRoutesDetailHitsRouteUUIDPath() async throws {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [RouteDetailMock.self]
        let client = MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
        let detail = try await client.forInstallation(id: 2012).routes.detail(routeUUID: "r1")
        XCTAssertEqual(detail.name, "Monthly Check")
        XCTAssertEqual(RouteDetailMock.lastPath, "/api/installations/2012/routes/r1")
    }
}

final class RouteDetailMock: URLProtocol {
    nonisolated(unsafe) static var lastPath: String?
    override class func canInit(with r: URLRequest) -> Bool { true }
    override class func canonicalRequest(for r: URLRequest) -> URLRequest { r }
    override func startLoading() {
        RouteDetailMock.lastPath = request.url?.path
        let body = #"{"uuid":"r1","name":"Monthly Check","description":"","section":null,"items":[]}"#
        let resp = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: "HTTP/1.1", headerFields: ["Content-Type":"application/json"])!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}
