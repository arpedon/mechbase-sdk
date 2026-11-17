import XCTest
@testable import Mechbase

/// `assets.addPhoto` / `measurementPoints.addPhoto` (mechbase-web#405).
final class PhotoUploadTests: XCTestCase {
    private func client() -> MechbaseClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [PhotoMock.self]
        return MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
    }

    private func jpg() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("p.jpg")
        try Data([1, 2]).write(to: url)
        return url
    }

    func testAssetPhotoPath() async throws {
        let out = try await client().forInstallation(id: 2012).assets.addPhoto(assetId: 10, fileURL: jpg(), uuid: "u-1")
        XCTAssertTrue(PhotoMock.lastPath?.hasSuffix("/api/installations/2012/assets/10/photos/") ?? false)
        XCTAssertEqual(out.uuid, "f1")
    }

    func testPointPhotoPath() async throws {
        _ = try await client().forInstallation(id: 2012).measurementPoints.addPhoto(pointId: 44, fileURL: jpg())
        XCTAssertTrue(PhotoMock.lastPath?.hasSuffix("/api/installations/2012/measurement-points/44/photos/") ?? false)
    }
}

final class PhotoMock: URLProtocol {
    nonisolated(unsafe) static var lastPath: String?
    override class func canInit(with r: URLRequest) -> Bool { true }
    override class func canonicalRequest(for r: URLRequest) -> URLRequest { r }
    override func startLoading() {
        PhotoMock.lastPath = request.url?.absoluteString
        let body = #"{"uuid":"f1","name":"p.jpg","kind":"attachment","file_url":"https://x/p.jpg","created_at":"2026-01-01T00:00:00Z"}"#
        let resp = HTTPURLResponse(url: request.url!, statusCode: 201, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8)); client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

/// `photos` on assets/points and `deletePhoto` (photo-delete contract §3).
final class PhotoDeleteTests: XCTestCase {
    private func client() -> MechbaseClient {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.protocolClasses = [MockURLProtocol.self]
        return MechbaseClient(token: "t", baseURL: URL(string: "https://x.test")!, session: URLSession(configuration: cfg))
    }
    override func tearDown() { MockURLProtocol.handler = nil; super.tearDown() }

    private func reply(_ status: Int, _ body: String = "", seen: @escaping @Sendable (URLRequest) -> Void = { _ in }) {
        MockURLProtocol.handler = { req in seen(req); return (status, Data(body.utf8)) }
    }

    func testPhotosDecodeAndDefaultEmpty() async throws {
        reply(200, #"{"uuid":"a","name":"Pump","status":1,"image_urls":["https://x/a.jpg"],"photos":[{"uuid":"f1","url":"https://x/a.jpg"}]}"#)
        let asset = try await client().forInstallation(id: 1).assets.get(id: 10)
        XCTAssertEqual(asset.photos, [Photo(uuid: "f1", url: "https://x/a.jpg")])
        reply(200, #"{"uuid":"p","name":"DE","status":1}"#)
        let point = try await client().forInstallation(id: 1).measurementPoints.get(id: 44)
        XCTAssertEqual(point.photos, [])
    }

    func testDeletePhotoHitsDeleteOnPhotoPath() async throws {
        nonisolated(unsafe) var seen: [String] = []
        reply(204) { seen.append("\($0.httpMethod!) \($0.url!.path)") }
        try await client().forInstallation(id: 2012).assets.deletePhoto(assetId: 10, uuid: "6f1c0000-0000-4000-8000-000000000001")
        try await client().forInstallation(id: 2012).measurementPoints.deletePhoto(pointId: 44, uuid: "6F1C0000-0000-4000-8000-000000000002")
        XCTAssertEqual(seen, [
            "DELETE /api/installations/2012/assets/10/photos/6f1c0000-0000-4000-8000-000000000001",
            "DELETE /api/installations/2012/measurement-points/44/photos/6F1C0000-0000-4000-8000-000000000002",
        ])
    }

    func testDeletePhoto404IsNotFound() async throws {
        reply(404, #"{"detail":"Not Found"}"#)
        for call in [
            { try await self.client().forInstallation(id: 1).assets.deletePhoto(assetId: 10, uuid: "6f1c0000-0000-4000-8000-000000000001") },
            { try await self.client().forInstallation(id: 1).measurementPoints.deletePhoto(pointId: 44, uuid: "6f1c0000-0000-4000-8000-000000000001") },
        ] as [() async throws -> Void] {
            do { try await call(); XCTFail("expected notFound") } catch MechbaseError.notFound {}
        }
    }

    func testDeletePhotoRejectsNonUUIDWithoutRequest() async throws {
        nonisolated(unsafe) var sent = 0
        reply(204) { _ in sent += 1 }
        for bad in ["../../10", "a?b", "f1"] {
            do { try await client().forInstallation(id: 1).assets.deletePhoto(assetId: 10, uuid: bad); XCTFail(bad) }
            catch MechbaseError.validation {}
        }
        XCTAssertEqual(sent, 0)
    }
}
