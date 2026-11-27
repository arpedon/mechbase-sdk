import Foundation

// A zone's own documents (plus its type's, `inherited`) and its photo gallery.

extension Zones {
    public func documents(zoneId: Int) async throws -> [ZoneDocument] {
        try await scope.http.get(scope.path("/zones/\(zoneId)/documents"), as: [ZoneDocument].self)
    }

    /// Upload `file`. `filename` defaults to "document.pdf" when empty (the server rejects names without an
    /// extension); `kind` is attachment | drawing | datasheet | manual | check_sheet | test_report; a
    /// client-minted `uuid` makes a retry safe.
    public func addDocument(zoneId: Int, file: Data, filename: String = "", kind: String = "attachment",
                            uuid: String? = nil, mimeType: String = "application/octet-stream") async throws -> ZoneDocument {
        var fields = ["kind": kind.isEmpty ? "attachment" : kind]
        if let uuid { fields["uuid"] = uuid }
        return try await scope.http.postMultipart(
            scope.path("/zones/\(zoneId)/documents"), fields: fields,
            files: [(name: "file", filename: filename.isEmpty ? "document.pdf" : filename, mimeType: mimeType, data: file)],
            as: ZoneDocument.self)
    }

    /// The zone's own documents only (an inherited one belongs to its type). 404 when already gone.
    public func deleteDocument(zoneId: Int, uuid: String) async throws {
        try requireUUID(uuid)
        _ = try await scope.http.delete(scope.path("/zones/\(zoneId)/documents/\(uuid)"), as: EmptyResponse.self)
    }

    /// By capture time, oldest first; unknown capture times last.
    public func photos(zoneId: Int) async throws -> [ZonePhoto] {
        try await scope.http.get(scope.path("/zones/\(zoneId)/photos"), as: [ZonePhoto].self)
    }

    /// Capture time comes from the file name or EXIF. A client-minted `uuid` makes a retry safe; the same
    /// file (name and size) again returns the photo already there.
    public func addPhoto(zoneId: Int, photo: PhotoUpload, uuid: String? = nil) async throws -> ZonePhoto {
        try await scope.http.postMultipart(
            scope.path("/zones/\(zoneId)/photos"), fields: uuid.map { ["uuid": $0] } ?? [:],
            files: [(name: "file", filename: photo.filename, mimeType: photo.mimeType, data: photo.data)],
            as: ZonePhoto.self)
    }

    /// 404 when already deleted.
    public func deletePhoto(zoneId: Int, uuid: String) async throws {
        try requireUUID(uuid)
        _ = try await scope.http.delete(scope.path("/zones/\(zoneId)/photos/\(uuid)"), as: EmptyResponse.self)
    }
}

public struct ZoneDocument: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let kind: String
    public let url: String
    public let createdAt: String
    public let inherited: Bool
    enum CodingKeys: String, CodingKey {
        case uuid, name, kind, url, inherited
        case createdAt = "created_at"
    }
}

public struct ZonePhoto: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let url: String
    public let takenAt: String?
    public let createdAt: String
    enum CodingKeys: String, CodingKey {
        case uuid, name, url
        case takenAt = "taken_at", createdAt = "created_at"
    }
}
