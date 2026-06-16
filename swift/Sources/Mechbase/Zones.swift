import Foundation

/// Create/upsert/update body for zones. Nil fields are omitted by the encoder.
public struct ZoneInput: Encodable, Sendable {
    public var name: String?
    public var externalId: String?
    public var sectionId: Int?
    public var sectionExternalId: String?

    public init(name: String? = nil, externalId: String? = nil,
                sectionId: Int? = nil, sectionExternalId: String? = nil) {
        self.name = name
        self.externalId = externalId
        self.sectionId = sectionId
        self.sectionExternalId = sectionExternalId
    }

    enum CodingKeys: String, CodingKey {
        case name
        case externalId = "external_id"
        case sectionId = "section_id"
        case sectionExternalId = "section_external_id"
    }
}

public struct Zones: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    public func list(query: String? = nil, sectionId: Int? = nil, limit: Int = 50, offset: Int = 0) async throws -> [Zone] {
        let q: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "section_id", value: sectionId.map(String.init)),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        return try await scope.http.get(scope.path("/zones"), query: q, as: Page<Zone>.self).items
    }

    public func get(id: Int) async throws -> Zone {
        try await scope.http.get(scope.path("/zones/\(id)"), as: Zone.self)
    }

    public func create(_ input: ZoneInput) async throws -> Zone {
        try await scope.http.postJSON(scope.path("/zones"), body: input, as: Zone.self)
    }

    public func upsert(_ input: ZoneInput) async throws -> Zone {
        try await scope.http.putJSON(scope.path("/zones"), body: input, as: Zone.self)
    }

    public func update(id: Int, _ input: ZoneInput) async throws -> Zone {
        try await scope.http.patchJSON(scope.path("/zones/\(id)"), body: input, as: Zone.self)
    }

    public func delete(id: Int, cascade: Bool = false) async throws -> DeleteResult {
        let q = cascade ? [URLQueryItem(name: "cascade", value: "true")] : []
        return try await scope.http.delete(scope.path("/zones/\(id)"), query: q, as: DeleteResult.self)
    }
}
