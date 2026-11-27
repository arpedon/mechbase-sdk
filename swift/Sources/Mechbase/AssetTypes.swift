import Foundation

/// Upsert/update body for asset types. Nil fields are omitted by the encoder.
public struct AssetTypeInput: Encodable, Sendable {
    public var code: String?
    public var name: String?
    public var manufacturer: String?
    public var checklist: [JSONValue]?
    public var externalId: String?

    public init(code: String? = nil, name: String? = nil, manufacturer: String? = nil,
                checklist: [JSONValue]? = nil, externalId: String? = nil) {
        self.code = code
        self.name = name
        self.manufacturer = manufacturer
        self.checklist = checklist
        self.externalId = externalId
    }

    enum CodingKeys: String, CodingKey {
        case code, name, manufacturer, checklist
        case externalId = "external_id"
    }
}

/// Asset types (templates), addressed by `code`: name, manufacturer, checklist and documents.
public struct AssetTypes: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    private func path(_ code: String, _ suffix: String = "") throws -> String {
        guard let c = code.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed.subtracting(CharacterSet(charactersIn: "/"))),
              !c.isEmpty else { throw MechbaseError.validation("invalid asset type code: \(code)") }
        return scope.path("/asset-types/\(c)\(suffix)")
    }

    public func list() async throws -> [AssetType] {
        try await scope.http.get(scope.path("/asset-types"), as: [AssetType].self)
    }

    public func get(code: String) async throws -> AssetType {
        try await scope.http.get(try path(code), as: AssetType.self)
    }

    /// Create or update the type keyed on `input.code`.
    public func upsert(_ input: AssetTypeInput) async throws -> AssetType {
        try await scope.http.putJSON(scope.path("/asset-types"), body: input, as: AssetType.self)
    }

    public func update(code: String, _ input: AssetTypeInput) async throws -> AssetType {
        try await scope.http.patchJSON(try path(code), body: input, as: AssetType.self)
    }

    public func delete(code: String) async throws -> DeleteResult {
        try await scope.http.delete(try path(code), as: DeleteResult.self)
    }

    public func documents(code: String) async throws -> [Document] {
        try await scope.http.get(try path(code, "/documents"), as: [Document].self)
    }

    /// Upload a document; same defaults as ``Documents/add(assetId:file:filename:kind:uuid:mimeType:)``.
    public func addDocument(code: String, file: Data, filename: String = "", kind: String = "attachment",
                            uuid: String? = nil, mimeType: String = "application/octet-stream") async throws -> Document {
        var fields = ["kind": kind.isEmpty ? "attachment" : kind]
        if let uuid { fields["uuid"] = uuid }
        return try await scope.http.postMultipart(
            try path(code, "/documents"),
            fields: fields,
            files: [(name: "file", filename: filename.isEmpty ? "document.pdf" : filename, mimeType: mimeType, data: file)],
            as: Document.self)
    }

    public func deleteDocument(code: String, uuid: String) async throws {
        guard UUID(uuidString: uuid) != nil else { throw MechbaseError.validation("invalid uuid: \(uuid)") }
        _ = try await scope.http.delete(try path(code, "/documents/\(uuid)"), as: EmptyResponse.self)
    }
}
