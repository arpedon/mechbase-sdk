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

    public init(name: String? = nil, externalId: String? = nil, sectionId: Int? = nil,
                sectionExternalId: String? = nil, zoneId: Int? = nil, zoneExternalId: String? = nil,
                equipmentType: String? = nil, machineClass: String? = nil) {
        self.name = name; self.externalId = externalId; self.sectionId = sectionId
        self.sectionExternalId = sectionExternalId; self.zoneId = zoneId
        self.zoneExternalId = zoneExternalId; self.equipmentType = equipmentType
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
}
