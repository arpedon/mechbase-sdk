import Foundation

// Route editor: route and check CRUD, reorder, check photo and history. Client-minted uuids make
// creates retry-safe (a retry returns the existing row; a uuid that belongs elsewhere is 409).

/// One check of a new route, or a check appended with ``Routes/addItem(routeUUID:_:)``.
public struct RouteItemInput: Encodable, Sendable {
    public var uuid: String?
    public var label: String
    /// pass_fail | numerical | multi_check | measurement.
    public var itemType: String
    public var instructions: String
    public var unit: String
    /// A multi_check's steps (at least one).
    public var subchecks: [String]
    public var assetId: Int?
    public var zoneId: Int?
    /// Required for a measurement check (its asset is taken when `assetId` is nil).
    public var measurementPointId: Int?

    public init(uuid: String? = nil, label: String, itemType: String = "pass_fail", instructions: String = "",
                unit: String = "", subchecks: [String] = [], assetId: Int? = nil, zoneId: Int? = nil,
                measurementPointId: Int? = nil) {
        self.uuid = uuid; self.label = label; self.itemType = itemType; self.instructions = instructions
        self.unit = unit; self.subchecks = subchecks; self.assetId = assetId; self.zoneId = zoneId
        self.measurementPointId = measurementPointId
    }

    enum CodingKeys: String, CodingKey {
        case uuid, label, instructions, unit, subchecks
        case itemType = "item_type", assetId = "asset_id", zoneId = "zone_id", measurementPointId = "measurement_point_id"
    }
}

/// A check edit: nil fields keep their value. `subchecks` replaces a multi-check's steps (required when
/// changing to multi_check); a check cannot change to or from measurement.
public struct RouteItemPatch: Encodable, Sendable {
    public var label: String?
    public var itemType: String?
    public var instructions: String?
    public var unit: String?
    public var subchecks: [String]?

    public init(label: String? = nil, itemType: String? = nil, instructions: String? = nil, unit: String? = nil,
                subchecks: [String]? = nil) {
        self.label = label; self.itemType = itemType; self.instructions = instructions; self.unit = unit
        self.subchecks = subchecks
    }

    enum CodingKeys: String, CodingKey { case label, instructions, unit, subchecks, itemType = "item_type" }
}

/// One check's place for ``Routes/reorderItems(routeUUID:_:)``: `position` within its stop. For
/// `zoneId` / `assetId`, nil keeps it where it is and `.some(nil)` clears it.
public struct ReorderEntry: Encodable, Sendable {
    public var uuid: String
    public var position: Int
    public var zoneId: Int??
    public var assetId: Int??

    /// - Warning: `zoneId` and `assetId` are `Int??`. Leaving the argument out (or a literal `nil`) keeps
    ///   the check where it is. Passing an **optional variable that is nil** sends an explicit `null`,
    ///   which CLEARS the zone/asset. Unwrap first if you mean "leave unchanged".
    public init(uuid: String, position: Int, zoneId: Int?? = nil, assetId: Int?? = nil) {
        self.uuid = uuid; self.position = position; self.zoneId = zoneId; self.assetId = assetId
    }

    enum CodingKeys: String, CodingKey { case uuid, position, zoneId = "zone_id", assetId = "asset_id" }
}

extension Routes {
    private struct CreateBody: Encodable { let uuid: String?; let name: String; let description: String; let items: [RouteItemInput] }
    private struct PatchBody: Encodable { let name: String?; let description: String? }
    private struct ReorderBody: Encodable { let items: [ReorderEntry] }
    private struct ReorderReply: Decodable { let items: [CheckNumber] }

    private func routePath(_ routeUUID: String, _ suffix: String = "") throws -> String {
        try requireUUID(routeUUID)
        return scope.path("/routes/\(routeUUID)\(suffix)")
    }

    private func itemPath(_ routeUUID: String, _ itemUUID: String, _ suffix: String = "") throws -> String {
        try requireUUID(itemUUID)
        return try routePath(routeUUID, "/items/\(itemUUID)\(suffix)")
    }

    /// Create a route with at least one check, `items` in reading order.
    public func create(name: String, description: String = "", items: [RouteItemInput],
                       uuid: String? = nil) async throws -> RouteDetail {
        try await scope.http.postJSON(scope.path("/routes"),
                                      body: CreateBody(uuid: uuid, name: name, description: description, items: items),
                                      as: RouteDetail.self)
    }

    /// Nil fields keep their value.
    public func update(routeUUID: String, name: String? = nil, description: String? = nil) async throws -> Route {
        try await scope.http.patchJSON(try routePath(routeUUID), body: PatchBody(name: name, description: description),
                                       as: Route.self)
    }

    /// Deletes the route with its runs. 409 while a run is in progress and for an asset's checklist route.
    public func delete(routeUUID: String) async throws {
        _ = try await scope.http.delete(try routePath(routeUUID), as: EmptyResponse.self)
    }

    /// Append a check at the end of the route. 409 on an asset's checklist route.
    public func addItem(routeUUID: String, _ item: RouteItemInput) async throws -> RouteItem {
        try await scope.http.postJSON(try routePath(routeUUID, "/items"), body: item, as: RouteItem.self)
    }

    public func updateItem(routeUUID: String, itemUUID: String, _ patch: RouteItemPatch) async throws -> RouteItem {
        try await scope.http.patchJSON(try itemPath(routeUUID, itemUUID), body: patch, as: RouteItem.self)
    }

    /// A check that past runs answered is archived instead, so their reports keep it.
    public func deleteItem(routeUUID: String, itemUUID: String) async throws {
        _ = try await scope.http.delete(try itemPath(routeUUID, itemUUID), as: EmptyResponse.self)
    }

    /// The board's drag and drop. The route is renumbered; returns every check's new `checkId`.
    public func reorderItems(routeUUID: String, _ entries: [ReorderEntry]) async throws -> [CheckNumber] {
        try await scope.http.postJSON(try routePath(routeUUID, "/items/reorder"), body: ReorderBody(items: entries),
                                      as: ReorderReply.self).items
    }

    /// Set the check's photo (one per check: it replaces the previous one). A client-minted `uuid` makes a
    /// retry safe; a late retry of a superseded photo is 409 (keep the newer one).
    public func setItemPhoto(routeUUID: String, itemUUID: String, photo: PhotoUpload,
                             uuid: String? = nil) async throws -> FileAttachment {
        try await scope.http.postMultipart(try itemPath(routeUUID, itemUUID, "/photos"),
                                           fields: uuid.map { ["uuid": $0] } ?? [:],
                                           files: [(name: "file", filename: photo.filename, mimeType: photo.mimeType, data: photo.data)],
                                           as: FileAttachment.self)
    }

    /// The check's answers across runs, newest first.
    public func itemHistory(routeUUID: String, itemUUID: String, limit: Int = 50,
                            offset: Int = 0) async throws -> OffsetPage<ItemHistoryEntry> {
        try await scope.http.get(try itemPath(routeUUID, itemUUID, "/history"),
                                 query: [URLQueryItem(name: "limit", value: String(limit)),
                                         URLQueryItem(name: "offset", value: String(offset))],
                                 as: OffsetPage<ItemHistoryEntry>.self)
    }
}

extension Assets {
    /// Re-read the asset type's checklist into the asset's checks route (`created` false). 422 once a
    /// run was completed, while one is open, or without a checks route or checklist.
    public func rebuildChecklist(assetId: Int) async throws -> ChecklistResult {
        try await scope.http.post(scope.path("/assets/\(assetId)/checklist/rebuild"), as: ChecklistResult.self)
    }
}

public struct CheckNumber: Codable, Sendable {
    public let uuid: String
    public let checkId: Int
    enum CodingKeys: String, CodingKey {
        case uuid
        case checkId = "check_id"
    }
}
