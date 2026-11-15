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
