import Foundation

/// Create/upsert/update body for sections. Nil fields are omitted by the encoder.
public struct SectionInput: Encodable, Sendable {
    public var name: String?
    public var externalId: String?

    public init(name: String? = nil, externalId: String? = nil) {
        self.name = name
        self.externalId = externalId
    }

    enum CodingKeys: String, CodingKey {
        case name
        case externalId = "external_id"
    }
}

public struct Sections: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    public func list(query: String? = nil, limit: Int = 50, offset: Int = 0) async throws -> [Section] {
        let q: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        return try await scope.http.get(scope.path("/sections"), query: q, as: Page<Section>.self).items
    }

    public func get(id: Int) async throws -> Section {
        try await scope.http.get(scope.path("/sections/\(id)"), as: Section.self)
    }

    public func create(_ input: SectionInput) async throws -> Section {
        try await scope.http.postJSON(scope.path("/sections"), body: input, as: Section.self)
    }

    public func upsert(_ input: SectionInput) async throws -> Section {
        try await scope.http.putJSON(scope.path("/sections"), body: input, as: Section.self)
    }

    public func update(id: Int, _ input: SectionInput) async throws -> Section {
        try await scope.http.patchJSON(scope.path("/sections/\(id)"), body: input, as: Section.self)
    }

    public func delete(id: Int, cascade: Bool = false) async throws -> DeleteResult {
        let q = cascade ? [URLQueryItem(name: "cascade", value: "true")] : []
        return try await scope.http.delete(scope.path("/sections/\(id)"), query: q, as: DeleteResult.self)
    }
}
