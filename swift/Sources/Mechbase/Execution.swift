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
    public func respond(
        routeItemUUID: String,
        data: JSONValue,
        notes: String = "",
        photos: [PhotoUpload] = []
    ) async throws -> ItemResponse {
        let body = RespondBody(route_item_uuid: routeItemUUID, data: data, notes: notes)
        if photos.isEmpty {
            return try await scope.http.postJSON(url("/responses"), body: body, as: ItemResponse.self)
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
            as: ItemResponse.self
        )
    }

    /// Convenience overload that takes a `[String: Any]` data dictionary.
    public func respond(
        routeItemUUID: String,
        data: [String: Any],
        notes: String = "",
        photos: [PhotoUpload] = []
    ) async throws -> ItemResponse {
        try await respond(
            routeItemUUID: routeItemUUID,
            data: JSONValue.from(data),
            notes: notes,
            photos: photos
        )
    }

    // MARK: - addFieldItem

    private struct FieldItemBody: Encodable {
        let label: String
        let item_type: String
        let data: JSONValue
        let zone_id: Int?
        let asset_id: Int?
        let config: JSONValue
        let notes: String
    }

    /// Append a field-discovered item to the execution.
    @discardableResult
    public func addFieldItem(
        label: String,
        itemType: String = "pass_fail",
        data: JSONValue = .object([:]),
        zoneId: Int? = nil,
        assetId: Int? = nil,
        config: JSONValue = .object([:]),
        notes: String = ""
    ) async throws -> ItemResponse {
        let body = FieldItemBody(
            label: label,
            item_type: itemType,
            data: data,
            zone_id: zoneId,
            asset_id: assetId,
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
        assetId: Int? = nil,
        notes: String = ""
    ) async throws -> ItemResponse {
        try await addFieldItem(
            label: label,
            itemType: itemType,
            data: JSONValue.from(data),
            zoneId: zoneId,
            assetId: assetId,
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

    @discardableResult
    public func complete() async throws -> RouteExecution {
        try await scope.http.post(url("/complete"), as: RouteExecution.self)
    }
}
