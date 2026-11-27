import XCTest
@testable import Mechbase

final class ZoneFilesTests: ParityTestCase {
    func testDocuments() async throws {
        reply("ZoneDocumentOut", list: true)
        let docs = try await inst.zones.documents(zoneId: 4)
        XCTAssertEqual(url, "\(base)/zones/4/documents")
        XCTAssertTrue(docs.first?.inherited ?? false)
        reply("ZoneDocumentOut", status: 201)
        _ = try await inst.zones.addDocument(zoneId: 4, file: Data([1]), filename: "p.pdf", kind: "drawing", uuid: u1)
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(formField("kind"), "drawing")
        XCTAssertEqual(formField("uuid"), u1)
        XCTAssertTrue(bodyText.contains(#"filename="p.pdf""#))
        ParityMock.reset(status: 413, reply: #"{"detail":"too large"}"#)
        await expectError({ _ = try await self.inst.zones.addDocument(zoneId: 4, file: Data()) }) {
            if case .tooLarge = $0 { return true }; return false
        }
        ParityMock.reset(status: 204, reply: "")
        try await inst.zones.deleteDocument(zoneId: 4, uuid: u1)
        XCTAssertEqual(url, "\(base)/zones/4/documents/\(u1)")
    }

    func testPhotos() async throws {
        reply("ZonePhotoOut", nulls: true, list: true)
        let photos = try await inst.zones.photos(zoneId: 4)
        XCTAssertEqual(url, "\(base)/zones/4/photos")
        XCTAssertNil(photos.first?.takenAt)
        reply("ZonePhotoOut", status: 201)
        _ = try await inst.zones.addPhoto(zoneId: 4, photo: PhotoUpload(filename: "IMG_1.jpg", data: Data([1])), uuid: u2)
        XCTAssertEqual(formField("uuid"), u2)
        ParityMock.reset(status: 204, reply: "")
        try await inst.zones.deletePhoto(zoneId: 4, uuid: u2)
        XCTAssertEqual(method, "DELETE")
        XCTAssertEqual(url, "\(base)/zones/4/photos/\(u2)")
    }
}
