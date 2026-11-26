import Foundation

/// Create/upsert/update body for assets. Nil fields are omitted by the encoder
/// (the SDK JSONEncoder skips nil optionals).
public struct AssetInput: Encodable, Sendable {
    public var name: String?
    public var externalId: String?
    public var sectionId: Int?
    public var sectionExternalId: String?
    public var zoneId: Int?
    public var zoneExternalId: String?
    public var equipmentType: String?
    public var machineClass: String?
    /// Type code. nil omits the field (leaves it untouched); `.some(nil)` sends explicit null (clears it).
    public var assetType: String??

    public init(name: String? = nil, externalId: String? = nil, sectionId: Int? = nil,
                sectionExternalId: String? = nil, zoneId: Int? = nil, zoneExternalId: String? = nil,
                equipmentType: String? = nil, machineClass: String? = nil, assetType: String?? = nil) {
        self.assetType = assetType
        self.name = name
        self.externalId = externalId
        self.sectionId = sectionId
        self.sectionExternalId = sectionExternalId
        self.zoneId = zoneId
        self.zoneExternalId = zoneExternalId
        self.equipmentType = equipmentType
        self.machineClass = machineClass
    }

    enum CodingKeys: String, CodingKey {
        case name
        case externalId = "external_id"
        case sectionId = "section_id"
        case sectionExternalId = "section_external_id"
        case zoneId = "zone_id"
        case zoneExternalId = "zone_external_id"
        case equipmentType = "equipment_type"
        case machineClass = "machine_class"
        case assetType = "asset_type"
    }
}

public struct Assets: Sendable {
    let scope: InstallationScope
    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    public func list(query: String? = nil, zoneId: Int? = nil, limit: Int = 50, offset: Int = 0) async throws -> [Asset] {
        let q: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "zone_id", value: zoneId.map(String.init)),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        return try await scope.http.get(scope.path("/assets"), query: q, as: Page<Asset>.self).items
    }

    public func get(id: Int) async throws -> Asset {
        try await scope.http.get(scope.path("/assets/\(id)"), as: Asset.self)
    }

    public func create(_ input: AssetInput) async throws -> Asset {
        try await scope.http.postJSON(scope.path("/assets"), body: input, as: Asset.self)
    }

    public func upsert(_ input: AssetInput) async throws -> Asset {
        try await scope.http.putJSON(scope.path("/assets"), body: input, as: Asset.self)
    }

    public func update(id: Int, _ input: AssetInput) async throws -> Asset {
        try await scope.http.patchJSON(scope.path("/assets/\(id)"), body: input, as: Asset.self)
    }

    public func delete(id: Int, cascade: Bool = false) async throws -> DeleteResult {
        let q = cascade ? [URLQueryItem(name: "cascade", value: "true")] : []
        return try await scope.http.delete(scope.path("/assets/\(id)"), query: q, as: DeleteResult.self)
    }

    /// Create (or find) the asset's checklist route from its type. 422 if the asset has no type or the type's checklist is empty.
    public func ensureChecklist(assetId: Int) async throws -> ChecklistResult {
        try await scope.http.post(scope.path("/assets/\(assetId)/checklist"), as: ChecklistResult.self)
    }

    /// Append a photo to the asset's gallery. Pass a client-minted `uuid` so a retry returns the same photo.
    public func addPhoto(assetId: Int, fileURL: URL, mimeType: String = "image/jpeg",
                         uuid: String? = nil) async throws -> FileAttachment {
        let data = try Data(contentsOf: fileURL)
        return try await scope.http.postMultipart(
            scope.path("/assets/\(assetId)/photos/"),
            fields: uuid.map { ["uuid": $0] } ?? [:],
            files: [(name: "file", filename: fileURL.lastPathComponent, mimeType: mimeType, data: data)],
            as: FileAttachment.self)
    }

    /// Delete a gallery photo by its ``Photo/uuid``. A photo that's already gone throws ``MechbaseError/notFound(_:)``; a non-UUID `uuid` throws ``MechbaseError/validation(_:)`` without a request.
    public func deletePhoto(assetId: Int, uuid: String) async throws {
        // Interpolated into the path: anything but a UUID could reroute or truncate it.
        guard UUID(uuidString: uuid) != nil else { throw MechbaseError.validation("invalid photo uuid: \(uuid)") }
        _ = try await scope.http.delete(scope.path("/assets/\(assetId)/photos/\(uuid)"), as: EmptyResponse.self)
    }
}
