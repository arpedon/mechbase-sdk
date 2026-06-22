import Foundation

/// Handle for an in-progress route execution. Returned by `Routes.start(...)`.
public struct Execution: Sendable {
    let scope: InstallationScope
    public let execution: RouteExecution

    init(scope: InstallationScope, execution: RouteExecution) {
        self.scope = scope
        self.execution = execution
    }

    public var uuid: String { execution.uuid }

    private func url(_ suffix: String) -> String {
        scope.path("/executions/\(uuid)\(suffix)")
    }

    // MARK: - respond

    private struct RespondBody: Encodable {
        let route_item_uuid: String
        let data: JSONValue
        let notes: String
    }

    /// Submit a response for a route item.
    ///
    /// When `idempotencyKey` is supplied it is sent as the `X-Idempotency-Key`
    /// header so the server can dedupe retries of the same logical response
    /// (the client uses the local response id as the key). Photo uploads use a
    /// multipart request; the header is applied there too.
    public func respond(
        routeItemUUID: String,
        data: JSONValue,
        notes: String = "",
        photos: [PhotoUpload] = [],
        idempotencyKey: String? = nil
    ) async throws -> ItemResponse {
        let body = RespondBody(route_item_uuid: routeItemUUID, data: data, notes: notes)
        let headers = idempotencyKey.map { ["X-Idempotency-Key": $0] } ?? [:]
        if photos.isEmpty {
            return try await scope.http.postJSON(url("/responses"), body: body, headers: headers, as: ItemResponse.self)
        }
        let payloadJSON = try JSONEncoder().encode(body)
        let payloadStr = String(data: payloadJSON, encoding: .utf8) ?? "{}"
        let files = photos.map {
            (name: "files", filename: $0.filename, mimeType: $0.mimeType, data: $0.data)
        }
        return try await scope.http.postMultipart(
            url("/responses/upload"),
            fields: ["payload": payloadStr],
            files: files,
            headers: headers,
            as: ItemResponse.self
        )
    }

    /// Convenience overload that takes a `[String: Any]` data dictionary.
    public func respond(
        routeItemUUID: String,
        data: [String: Any],
        notes: String = "",
        photos: [PhotoUpload] = [],
        idempotencyKey: String? = nil
    ) async throws -> ItemResponse {
        try await respond(
            routeItemUUID: routeItemUUID,
            data: JSONValue.from(data),
            notes: notes,
            photos: photos,
            idempotencyKey: idempotencyKey
        )
    }

    // MARK: - addFieldItem

    private struct FieldItemBody: Encodable {
        let label: String
        let item_type: String
        let data: JSONValue
        let zone_id: Int?
        let config: JSONValue
        let notes: String
    }

    /// Append a field-discovered item to the execution.
    ///
    /// Items are zone-anchored (`zoneId`) or route-level (`nil`). Bind the item
    /// to a specific asset after the walk via ``triage(routeItemUUID:assetId:)``.
    @discardableResult
    public func addFieldItem(
        label: String,
        itemType: String = "pass_fail",
        data: JSONValue = .object([:]),
        zoneId: Int? = nil,
        config: JSONValue = .object([:]),
        notes: String = ""
    ) async throws -> ItemResponse {
        let body = FieldItemBody(
            label: label,
            item_type: itemType,
            data: data,
            zone_id: zoneId,
            config: config,
            notes: notes
        )
        return try await scope.http.postJSON(url("/items"), body: body, as: ItemResponse.self)
    }

    /// Convenience overload accepting a `[String: Any]` data dictionary.
    @discardableResult
    public func addFieldItem(
        label: String,
        itemType: String = "pass_fail",
        data: [String: Any],
        zoneId: Int? = nil,
        notes: String = ""
    ) async throws -> ItemResponse {
        try await addFieldItem(
            label: label,
            itemType: itemType,
            data: JSONValue.from(data),
            zoneId: zoneId,
            notes: notes
        )
    }

    // MARK: - triage

    private struct TriageBody: Encodable {
        let route_item_uuid: String
        let asset_id: Int
    }

    @discardableResult
    public func triage(routeItemUUID: String, assetId: Int) async throws -> ItemResponse {
        let body = TriageBody(route_item_uuid: routeItemUUID, asset_id: assetId)
        return try await scope.http.postJSON(url("/triage"), body: body, as: ItemResponse.self)
    }

    // MARK: - complete

    /// Finalize the execution. When `idempotencyKey` is supplied it is sent as
    /// the `X-Idempotency-Key` header so the server can dedupe a retried
    /// completion (the client uses the execution uuid as the key).
    @discardableResult
    public func complete(idempotencyKey: String? = nil) async throws -> RouteExecution {
        let headers = idempotencyKey.map { ["X-Idempotency-Key": $0] } ?? [:]
        return try await scope.http.post(url("/complete"), headers: headers, as: RouteExecution.self)
    }
}
