import Foundation

// Run history and reports, amending a completed run, non-conformities, blank surveys.

/// One offset-paginated page; ask again with `offset + items.count` while it is below `total`.
public struct OffsetPage<T: Decodable & Sendable>: Decodable, Sendable {
    public let items: [T]
    public let total: Int
    public let limit: Int
    public let offset: Int
}

private func idempotency(_ key: String?) -> [String: String] {
    key.map { ["X-Idempotency-Key": $0] } ?? [:]
}

extension Routes {
    /// A route's runs, newest first (cancelled empty runs left out).
    public func executions(routeUUID: String, limit: Int = 50, offset: Int = 0) async throws -> OffsetPage<ExecutionSummary> {
        try requireUUID(routeUUID)
        return try await scope.http.get(scope.path("/routes/\(routeUUID)/executions"),
                                        query: [URLQueryItem(name: "limit", value: String(limit)),
                                                URLQueryItem(name: "offset", value: String(offset))],
                                        as: OffsetPage<ExecutionSummary>.self)
    }

    /// The run report: answered checks by stop (photos, linked readings), the unanswered ones,
    /// non-conformities worst first, totals. Works for a run in progress too.
    public func report(executionUUID: String) async throws -> ExecutionReport {
        try requireUUID(executionUUID)
        return try await scope.http.get(scope.path("/executions/\(executionUUID)/report"), as: ExecutionReport.self)
    }

    private struct NotesBody: Encodable { let notes: String }

    /// Replace a response's finding/recommendation text (the report's notes editor).
    public func updateResponseNotes(responseUUID: String, notes: String) async throws -> ItemResponse {
        try requireUUID(responseUUID)
        return try await scope.http.patchJSON(scope.path("/responses/\(responseUUID)"), body: NotesBody(notes: notes),
                                              as: ItemResponse.self)
    }

    /// Responses that were not Normal, newest run first. `status`: open | resolved | all.
    public func nonConformities(status: String = "open", assetId: Int? = nil, limit: Int = 50,
                                offset: Int = 0) async throws -> OffsetPage<NonConformity> {
        let q = [URLQueryItem(name: "status", value: status),
                 URLQueryItem(name: "asset_id", value: assetId.map(String.init)),
                 URLQueryItem(name: "limit", value: String(limit)),
                 URLQueryItem(name: "offset", value: String(offset))]
        return try await scope.http.get(scope.path("/non-conformities"), query: q, as: OffsetPage<NonConformity>.self)
    }

    private struct ResolveBody: Encodable { let comment: String }

    /// Resolve a non-conformity. A retry by the same person is 200; resolved by someone else is 409.
    public func resolveNonConformity(responseUUID: String, comment: String = "") async throws -> NonConformity {
        try requireUUID(responseUUID)
        return try await scope.http.postJSON(scope.path("/non-conformities/\(responseUUID)/resolve"),
                                             body: ResolveBody(comment: comment), as: NonConformity.self)
    }

    private struct SurveyBody: Encodable { let name: String; let uuid: String? }

    /// A new empty route and its first run in one step; add checks during the walk with
    /// ``Execution/addFieldItem(label:itemType:data:zoneId:config:notes:)``. A client-minted `uuid`
    /// (the run's) makes a retry safe.
    public func startSurvey(name: String = "", uuid: String? = nil) async throws -> Survey {
        try await scope.http.postJSON(scope.path("/surveys"), body: SurveyBody(name: name, uuid: uuid), as: Survey.self)
    }
}

// MARK: - Amend a completed run (staff or the runner)

extension Execution {
    private func amendPath(_ itemUUID: String, _ suffix: String) throws -> String {
        try requireUUID(uuid)
        try requireUUID(itemUUID)
        return scope.path("/executions/\(uuid)/amend/\(itemUUID)\(suffix)")
    }

    private struct AnswerBody: Encodable { let data: JSONValue; let notes: String }
    private struct NotesBody: Encodable { let notes: String }

    /// Answer a check the run left unanswered. With `idempotencyKey` a retry returns the answer it made.
    public func amendAnswer(itemUUID: String, data: JSONValue, notes: String = "",
                            idempotencyKey: String? = nil) async throws -> ItemResponse {
        try await scope.http.postJSON(try amendPath(itemUUID, "/answer"), body: AnswerBody(data: data, notes: notes),
                                      headers: idempotency(idempotencyKey), as: ItemResponse.self)
    }

    /// Replace a check's notes; the previous text stays in the run's amendment log.
    public func amendNotes(itemUUID: String, notes: String) async throws -> ItemResponse {
        try await scope.http.patchJSON(try amendPath(itemUUID, "/notes"), body: NotesBody(notes: notes),
                                       as: ItemResponse.self)
    }

    /// Add a photo to the check's response (or its reading, for a measurement check). A client-minted
    /// `uuid` makes a retry safe.
    public func amendAddPhoto(itemUUID: String, photo: PhotoUpload, uuid: String? = nil) async throws -> FileAttachment {
        try await scope.http.postMultipart(try amendPath(itemUUID, "/photos"),
                                           fields: uuid.map { ["uuid": $0] } ?? [:],
                                           files: [(name: "file", filename: photo.filename, mimeType: photo.mimeType, data: photo.data)],
                                           as: FileAttachment.self)
    }

    /// Take a photo off the check (it stays on the run). Repeating is a no-op.
    public func amendRemovePhoto(itemUUID: String, fileUUID: String) async throws {
        try requireUUID(fileUUID)
        _ = try await scope.http.delete(try amendPath(itemUUID, "/photos/\(fileUUID)"), as: EmptyResponse.self)
    }

    /// Record a new reading on a measurement check: `value` (the point type's main scalar), a comment,
    /// photos and a `dataFile` (thermography: required; vibration: a value or a waveform file). The
    /// previous reading stays in history. With `idempotencyKey` a retry returns the answer it made.
    public func amendReading(itemUUID: String, value: Double? = nil, comment: String = "", images: [PhotoUpload] = [],
                             dataFile: PhotoUpload? = nil, idempotencyKey: String? = nil) async throws -> ItemResponse {
        var fields = ["comment": comment]
        if let value { fields["value"] = String(value) }
        var files = images.map { (name: "images", filename: $0.filename, mimeType: $0.mimeType, data: $0.data) }
        if let f = dataFile { files.append((name: "data_file", filename: f.filename, mimeType: f.mimeType, data: f.data)) }
        return try await scope.http.postMultipart(try amendPath(itemUUID, "/reading"), fields: fields, files: files,
                                                  headers: idempotency(idempotencyKey), as: ItemResponse.self)
    }
}

/// One run in a route's history. Counts are over the run's responses, as the web's Runs table shows them:
/// ``passed_count``/``answered_count``.
public struct ExecutionSummary: Codable, Sendable {
    public let uuid: String
    public let routeUuid: String
    public let status: String
    public let startedAt: String?
    public let completedAt: String?
    public let sessionId: String
    public let number: Int
    public let executedBy: PersonRef?
    public let answeredCount: Int
    public let passedCount: Int
    public let nonConformityCount: Int
    public let maxStatus: Int?
    enum CodingKeys: String, CodingKey {
        case uuid, status, number
        case routeUuid = "route_uuid", startedAt = "started_at", completedAt = "completed_at"
        case sessionId = "session_id", executedBy = "executed_by", answeredCount = "answered_count"
        case passedCount = "passed_count", nonConformityCount = "non_conformity_count", maxStatus = "max_status"
    }
}

public struct ExecutionReport: Codable, Sendable {
    public let execution: ExecutionSummary
    public let route: Route
    public let canAmend: Bool
    public let totals: ReportTotals
    public let groups: [ReportGroup]
    public let missing: [ReportCheck]
    public let exceptions: [ReportException]
    enum CodingKeys: String, CodingKey {
        case execution, route, totals, groups, missing, exceptions
        case canAmend = "can_amend"
    }
}

public struct ReportTotals: Codable, Sendable {
    public let checks: Int
    public let answered: Int
    public let passed: Int
    public let nonConformities: Int
    enum CodingKeys: String, CodingKey {
        case checks, answered, passed
        case nonConformities = "non_conformities"
    }
}

public struct ReportGroup: Codable, Sendable {
    public let zoneId: Int?
    public let label: String
    public let entries: [ReportEntry]
    enum CodingKeys: String, CodingKey {
        case label, entries
        case zoneId = "zone_id"
    }
}

public struct ReportEntry: Codable, Sendable {
    public let check: ReportCheck
    public let response: ReportResponse
    enum CodingKeys: String, CodingKey {
        case check, response
    }
}

public struct ReportCheck: Codable, Sendable {
    public let uuid: String
    public let checkId: Int
    public let label: String
    public let itemType: String
    public let assetId: Int?
    public let assetName: String?
    public let zoneId: Int?
    public let measurementPointId: Int?
    public let config: JSONValue
    /// The instructions the technician read (HTML; the item's own, else its point's); nil on older servers.
    public let instructions: String?
    /// The point's alarm limit, for a measurement check.
    public let limit: MeasurementLimit?
    enum CodingKeys: String, CodingKey {
        case uuid, label, config, instructions, limit
        case checkId = "check_id", itemType = "item_type", assetId = "asset_id", assetName = "asset_name"
        case zoneId = "zone_id", measurementPointId = "measurement_point_id"
    }
}

public struct ReportResponse: Codable, Sendable {
    public let uuid: String
    public let data: JSONValue
    public let notes: String
    public let status: Int
    public let createdAt: String
    public let resolvedAt: String?
    public let resolvedBy: PersonRef?
    public let resolutionComment: String
    public let photos: [ReportPhoto]
    public let reading: LinkedReading?
    enum CodingKeys: String, CodingKey {
        case uuid, data, notes, status, photos, reading
        case createdAt = "created_at", resolvedAt = "resolved_at", resolvedBy = "resolved_by"
        case resolutionComment = "resolution_comment"
    }
}

public struct ReportPhoto: Codable, Sendable {
    public let uuid: String
    /// "photo", or "thermogram" for a thermography reading's image.
    public let kind: String
    public let url: String
    public let name: String
    enum CodingKeys: String, CodingKey {
        case uuid, kind, url, name
    }
}

/// The Measurement a measurement check's response links to.
public struct LinkedReading: Codable, Sendable {
    public let uuid: String
    public let pointId: Int?
    public let pointSequence: Int?
    public let status: Int
    public let data: JSONValue
    public let notes: String
    public let createdAt: String
    enum CodingKeys: String, CodingKey {
        case uuid, status, data, notes
        case pointId = "point_id", pointSequence = "point_sequence", createdAt = "created_at"
    }
}

public struct ReportException: Codable, Sendable {
    public let responseUuid: String
    public let routeItemUuid: String
    public let name: String
    public let status: Int
    public let resolved: Bool
    enum CodingKeys: String, CodingKey {
        case name, status, resolved
        case responseUuid = "response_uuid", routeItemUuid = "route_item_uuid"
    }
}

public struct NonConformity: Codable, Sendable {
    public let responseUuid: String
    public let executionUuid: String
    public let routeUuid: String
    public let routeName: String
    public let routeItemUuid: String
    public let label: String
    public let assetId: Int?
    public let assetName: String?
    public let status: Int
    public let notes: String
    public let startedAt: String?
    public let createdAt: String
    public let resolvedAt: String?
    public let resolvedBy: PersonRef?
    public let resolutionComment: String
    enum CodingKeys: String, CodingKey {
        case label, status, notes
        case responseUuid = "response_uuid", executionUuid = "execution_uuid", routeUuid = "route_uuid"
        case routeName = "route_name", routeItemUuid = "route_item_uuid", assetId = "asset_id"
        case assetName = "asset_name"
        case startedAt = "started_at", createdAt = "created_at", resolvedAt = "resolved_at"
        case resolvedBy = "resolved_by", resolutionComment = "resolution_comment"
    }
}

public struct Survey: Codable, Sendable {
    public let route: Route
    public let execution: RouteExecution
    enum CodingKeys: String, CodingKey {
        case route, execution
    }
}

public struct ItemHistoryEntry: Codable, Sendable {
    public let responseUuid: String
    public let executionUuid: String
    public let executionStatus: String
    public let executedBy: PersonRef?
    public let startedAt: String?
    public let createdAt: String
    public let status: Int
    public let data: JSONValue
    public let notes: String
    public let measurementUuid: String?
    public let pointSequence: Int?
    enum CodingKeys: String, CodingKey {
        case status, data, notes
        case responseUuid = "response_uuid", executionUuid = "execution_uuid"
        case executionStatus = "execution_status", executedBy = "executed_by", startedAt = "started_at"
        case createdAt = "created_at", measurementUuid = "measurement_uuid", pointSequence = "point_sequence"
    }
}
