import Foundation

/// A comment's pointer at a measurement point, optionally one reading.
public struct CommentReference: Codable, Sendable, Equatable {
    public let pointId: Int?
    public let pointSequence: Int?
    enum CodingKeys: String, CodingKey { case pointId = "point_id", pointSequence = "point_sequence" }
}

/// What to attach to a comment: point `pointId` of the asset, optionally one reading by `pointSequence`.
public struct CommentReferenceIn: Codable, Sendable, Equatable {
    public let pointId: Int
    public let pointSequence: Int?
    public init(pointId: Int, pointSequence: Int? = nil) { self.pointId = pointId; self.pointSequence = pointSequence }
    enum CodingKeys: String, CodingKey { case pointId = "point_id", pointSequence = "point_sequence" }
}

/// One entry in an asset's thread. `body` is rich-text HTML; `editable` is false for other authors' and findings' notes.
public struct Comment: Codable, Sendable {
    public let id: Int
    public let body: String
    public let bodyText: String
    public let authorName: String
    public let createdAt: String
    public let editedAt: String?
    public let references: [CommentReference]
    public let isFinding: Bool
    public let editable: Bool

    enum CodingKeys: String, CodingKey {
        case id, body, references, editable
        case bodyText = "body_text", authorName = "author_name", createdAt = "created_at"
        case editedAt = "edited_at", isFinding = "is_finding"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func str(_ k: CodingKeys) -> String { (try? c.decode(String.self, forKey: k)) ?? "" }
        self.id = try c.decode(Int.self, forKey: .id)
        self.body = str(.body)
        self.bodyText = str(.bodyText)
        self.authorName = str(.authorName)
        self.createdAt = str(.createdAt)
        self.editedAt = try c.decodeIfPresent(String.self, forKey: .editedAt)
        self.references = (try? c.decode([CommentReference].self, forKey: .references)) ?? []
        self.isFinding = (try? c.decode(Bool.self, forKey: .isFinding)) ?? false
        self.editable = (try? c.decode(Bool.self, forKey: .editable)) ?? false
    }
}

public struct CommentsPage: Codable, Sendable {
    public let items: [Comment]
    public let total: Int
    public let limit: Int
    public let offset: Int

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.items = (try? c.decode([Comment].self, forKey: .items)) ?? []
        self.total = (try? c.decode(Int.self, forKey: .total)) ?? 0
        self.limit = (try? c.decode(Int.self, forKey: .limit)) ?? 0
        self.offset = (try? c.decode(Int.self, forKey: .offset)) ?? 0
    }
    enum CodingKeys: String, CodingKey { case items, total, limit, offset }
}

public struct Document: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let kind: String
    public let url: String
    public let createdAt: String

    enum CodingKeys: String, CodingKey { case uuid, name, kind, url, createdAt = "created_at" }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func str(_ k: CodingKeys) -> String { (try? c.decode(String.self, forKey: k)) ?? "" }
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.name = str(.name)
        self.kind = str(.kind)
        self.url = str(.url)
        self.createdAt = str(.createdAt)
    }
}

/// `scope` is "point" or "installation" (read-only defaults).
public struct AlarmRule: Codable, Sendable {
    public let uuid: String
    public let scope: String
    public let method: String
    public let dataKey: String
    public let effectiveDataKey: String
    public let direction: String
    public let minorThreshold: Double?
    public let majorThreshold: Double?
    public let thresholdMode: String
    public let source: String?

    enum CodingKeys: String, CodingKey {
        case uuid, scope, method, direction, source
        case dataKey = "data_key", effectiveDataKey = "effective_data_key"
        case minorThreshold = "minor_threshold", majorThreshold = "major_threshold"
        case thresholdMode = "threshold_mode"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func str(_ k: CodingKeys) -> String { (try? c.decode(String.self, forKey: k)) ?? "" }
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.scope = str(.scope)
        self.method = str(.method)
        self.dataKey = str(.dataKey)
        self.effectiveDataKey = str(.effectiveDataKey)
        self.direction = str(.direction)
        self.minorThreshold = try c.decodeIfPresent(Double.self, forKey: .minorThreshold)
        self.majorThreshold = try c.decodeIfPresent(Double.self, forKey: .majorThreshold)
        self.thresholdMode = str(.thresholdMode)
        self.source = try c.decodeIfPresent(String.self, forKey: .source)
    }
}

/// An asset's comment thread. A 403 (``MechbaseError/auth(_:)``) means not the author, or a finding's note.
public final class Comments: Sendable {
    private let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    // Non-optional `references`: an empty set must still be sent.
    private struct Body: Encodable { let body: String; let references: [CommentReferenceIn] }

    public func list(assetId: Int, limit: Int? = nil, offset: Int? = nil) async throws -> CommentsPage {
        let q = [
            URLQueryItem(name: "limit", value: limit.map(String.init)),
            URLQueryItem(name: "offset", value: offset.map(String.init)),
        ]
        return try await scope.http.get(scope.path("/assets/\(assetId)/comments"), query: q, as: CommentsPage.self)
    }

    public func create(assetId: Int, body: String, references: [CommentReferenceIn] = []) async throws -> Comment {
        try await scope.http.postJSON(scope.path("/assets/\(assetId)/comments"),
                                      body: Body(body: body, references: references), as: Comment.self)
    }

    /// Replaces the body and the whole reference set.
    public func update(assetId: Int, commentId: Int, body: String, references: [CommentReferenceIn] = []) async throws -> Comment {
        try await scope.http.patchJSON(scope.path("/assets/\(assetId)/comments/\(commentId)"),
                                       body: Body(body: body, references: references), as: Comment.self)
    }

    public func delete(assetId: Int, commentId: Int) async throws {
        _ = try await scope.http.delete(scope.path("/assets/\(assetId)/comments/\(commentId)"), as: EmptyResponse.self)
    }
}

public final class Documents: Sendable {
    private let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    public func list(assetId: Int) async throws -> [Document] {
        try await scope.http.get(scope.path("/assets/\(assetId)/documents"), as: [Document].self)
    }

    /// Upload `file`. `filename` defaults to "document.pdf" when empty (the server rejects names without an extension);
    /// `kind` is attachment | drawing | datasheet | manual | check_sheet | test_report; a client-minted `uuid` makes retries idempotent.
    public func add(assetId: Int, file: Data, filename: String = "", kind: String = "attachment",
                    uuid: String? = nil, mimeType: String = "application/octet-stream") async throws -> Document {
        var fields = ["kind": kind.isEmpty ? "attachment" : kind]
        if let uuid { fields["uuid"] = uuid }
        return try await scope.http.postMultipart(
            scope.path("/assets/\(assetId)/documents"),
            fields: fields,
            files: [(name: "file", filename: filename.isEmpty ? "document.pdf" : filename, mimeType: mimeType, data: file)],
            as: Document.self)
    }

    public func delete(assetId: Int, uuid: String) async throws {
        guard UUID(uuidString: uuid) != nil else { throw MechbaseError.validation("invalid uuid: \(uuid)") }
        _ = try await scope.http.delete(scope.path("/assets/\(assetId)/documents/\(uuid)"), as: EmptyResponse.self)
    }
}

/// Point alarm rules. Only method=threshold point overrides are writable; installation defaults are read-only (403).
public final class AlarmRules: Sendable {
    private let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    private func path(_ pointId: Int, _ suffix: String = "") -> String {
        scope.path("/measurement-points/\(pointId)/alarm-rules\(suffix)")
    }

    private struct CreateBody: Encodable {
        let method = "threshold"
        let data_key: String
        let direction: String
        let minor_threshold: Double
        let major_threshold: Double
    }

    // nil fields are omitted by the synthesized encoder.
    private struct PatchBody: Encodable {
        let data_key: String?
        let direction: String?
        let minor_threshold: Double?
        let major_threshold: Double?
    }

    public func list(pointId: Int) async throws -> [AlarmRule] {
        try await scope.http.get(path(pointId), as: [AlarmRule].self)
    }

    /// 409 (``MechbaseError/conflict(_:)``) if the point already has an override.
    public func create(pointId: Int, minorThreshold: Double, majorThreshold: Double,
                       dataKey: String = "", direction: String = "high") async throws -> AlarmRule {
        try await scope.http.postJSON(path(pointId),
            body: CreateBody(data_key: dataKey, direction: direction, minor_threshold: minorThreshold, major_threshold: majorThreshold),
            as: AlarmRule.self)
    }

    /// Only non-nil arguments are sent.
    public func update(pointId: Int, uuid: String, minorThreshold: Double? = nil, majorThreshold: Double? = nil,
                       dataKey: String? = nil, direction: String? = nil) async throws -> AlarmRule {
        guard UUID(uuidString: uuid) != nil else { throw MechbaseError.validation("invalid uuid: \(uuid)") }
        return try await scope.http.patchJSON(path(pointId, "/\(uuid)"),
            body: PatchBody(data_key: dataKey, direction: direction, minor_threshold: minorThreshold, major_threshold: majorThreshold),
            as: AlarmRule.self)
    }

    public func delete(pointId: Int, uuid: String) async throws {
        guard UUID(uuidString: uuid) != nil else { throw MechbaseError.validation("invalid uuid: \(uuid)") }
        _ = try await scope.http.delete(path(pointId, "/\(uuid)"), as: EmptyResponse.self)
    }
}
