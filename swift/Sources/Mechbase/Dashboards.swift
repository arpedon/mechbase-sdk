import Foundation

/// One section of a board layout for ``Dashboards/reorder(dashboardUuid:sections:)``: the section's uuid
/// and its tile uuids in order (a tile may come from another section of the same board).
public struct LayoutSection: Encodable, Sendable {
    public var id: String
    public var tiles: [String]
    public init(id: String, tiles: [String] = []) { self.id = id; self.tiles = tiles }
}

/// Live dashboards. Reads are for every member; the writes are staff-only (gate on ``User/isStaff``).
///
/// Poll a board every ``Dashboard/refreshSeconds`` with the last ETag:
/// ```swift
/// switch try await inst.dashboards.get(etag: etag) {
/// case .modified(let board, let newEtag): show(board); etag = newEtag
/// case .notModified: break  // keep what is on screen
/// }
/// ```
public final class Dashboards: Sendable {
    private let scope: InstallationScope
    init(http: HTTPClient, installationId: Int) { scope = InstallationScope(http: http, installationId: installationId) }

    private func path(_ uuid: String, _ suffix: String = "") throws -> String {
        try requireUUID(uuid)
        return scope.path("/dashboards/\(uuid)\(suffix)")
    }

    /// Saved boards by position; with none saved, the automatic board alone (`uuid` nil).
    public func list() async throws -> [DashboardSummary] {
        try await scope.http.get(scope.path("/dashboards"), as: [DashboardSummary].self)
    }

    /// A board, sections → tiles. `dashboardUuid` nil is the default board (else the first, else the
    /// automatic one). Pass the ETag of the last `.modified` to get `.notModified` while nothing changed.
    public func get(dashboardUuid: String? = nil, etag: String? = nil) async throws -> Conditional<Dashboard> {
        let p = try dashboardUuid.map { try path($0) } ?? scope.path("/dashboards/default")
        return try await scope.http.getConditional(p, etag: etag, as: Dashboard.self)
    }

    private struct NameBody: Encodable { let name: String }
    private struct UpdateBody: Encodable { let name: String?; let is_default: Bool? }
    private struct TitleBody: Encodable { let title: String }
    private struct LabelBody: Encodable { let label: String }
    private struct LayoutBody: Encodable { let sections: [LayoutSection] }
    private struct TilesBody: Encodable { let section: String; let point_ids: [Int] }

    /// Blank name → "New dashboard". The installation's first board becomes its default.
    public func create(name: String = "") async throws -> DashboardSummary {
        try await scope.http.postJSON(scope.path("/dashboards"), body: NameBody(name: name), as: DashboardSummary.self)
    }

    /// Nil fields keep their value; `isDefault: true` clears the flag on every other board.
    public func update(dashboardUuid: String, name: String? = nil, isDefault: Bool? = nil) async throws -> DashboardSummary {
        try await scope.http.patchJSON(try path(dashboardUuid), body: UpdateBody(name: name, is_default: isDefault),
                                       as: DashboardSummary.self)
    }

    public func delete(dashboardUuid: String) async throws {
        _ = try await scope.http.delete(try path(dashboardUuid), as: EmptyResponse.self)
    }

    /// Save the automatic board as "All monitored points". 422 when no point has an active MaintNode mapping.
    public func saveAutomatic() async throws -> DashboardSummary {
        try await scope.http.post(scope.path("/dashboards/save-automatic"), as: DashboardSummary.self)
    }

    /// Sections in order, each with its tiles in order; sections or tiles left out keep their place.
    public func reorder(dashboardUuid: String, sections: [LayoutSection]) async throws {
        _ = try await scope.http.postJSON(try path(dashboardUuid, "/reorder"), body: LayoutBody(sections: sections),
                                          as: EmptyResponse.self)
    }

    /// Appended last. Blank title → "New section".
    public func addSection(dashboardUuid: String, title: String = "") async throws -> DashboardSection {
        try await scope.http.postJSON(try path(dashboardUuid, "/sections"), body: TitleBody(title: title),
                                      as: DashboardSection.self)
    }

    public func renameSection(dashboardUuid: String, sectionUuid: String, title: String) async throws -> DashboardSection {
        try requireUUID(sectionUuid)
        return try await scope.http.patchJSON(try path(dashboardUuid, "/sections/\(sectionUuid)"),
                                              body: TitleBody(title: title), as: DashboardSection.self)
    }

    /// Deletes its tiles too.
    public func deleteSection(dashboardUuid: String, sectionUuid: String) async throws {
        try requireUUID(sectionUuid)
        _ = try await scope.http.delete(try path(dashboardUuid, "/sections/\(sectionUuid)"), as: EmptyResponse.self)
    }

    /// Append points (per-installation ids) to `sectionUuid`; points already there are skipped, so the
    /// result lists only the new tiles.
    public func addTiles(dashboardUuid: String, sectionUuid: String, pointIds: [Int]) async throws -> [DashboardTileRef] {
        try requireUUID(sectionUuid)
        return try await scope.http.postJSON(try path(dashboardUuid, "/tiles"),
                                             body: TilesBody(section: sectionUuid, point_ids: pointIds),
                                             as: [DashboardTileRef].self)
    }

    /// Blank label falls back to the point's own.
    public func renameTile(dashboardUuid: String, tileUuid: String, label: String) async throws -> DashboardTileRef {
        try requireUUID(tileUuid)
        return try await scope.http.patchJSON(try path(dashboardUuid, "/tiles/\(tileUuid)"),
                                              body: LabelBody(label: label), as: DashboardTileRef.self)
    }

    public func removeTile(dashboardUuid: String, tileUuid: String) async throws {
        try requireUUID(tileUuid)
        _ = try await scope.http.delete(try path(dashboardUuid, "/tiles/\(tileUuid)"), as: EmptyResponse.self)
    }
}

/// A board in the picker. ``uuid`` is null for the automatic board.
public struct DashboardSummary: Codable, Sendable {
    public let uuid: String?
    public let name: String
    /// The board GET .../dashboards/default returns.
    public let isDefault: Bool
    public let isAutomatic: Bool
    enum CodingKeys: String, CodingKey {
        case uuid, name
        case isDefault = "is_default", isAutomatic = "is_automatic"
    }
}

public struct Dashboard: Codable, Sendable {
    public let uuid: String?
    public let name: String
    /// The board GET .../dashboards/default returns.
    public let isDefault: Bool
    public let isAutomatic: Bool
    public let refreshSeconds: Int
    /// Show sections as readiness + health instead of the status word.
    public let readiness: Bool
    public let sections: [BoardSection]
    enum CodingKeys: String, CodingKey {
        case uuid, name, readiness, sections
        case isDefault = "is_default", isAutomatic = "is_automatic", refreshSeconds = "refresh_seconds"
    }
}

public struct BoardSection: Codable, Sendable {
    /// Saved section id; null on the automatic board.
    public let uuid: String?
    public let title: String
    /// Automatic board: 'Section / Zone' of the asset.
    public let meta: String
    public let latest: String?
    /// Worst alarm tile's status, else 1.
    public let status: Int
    public let statusLabel: String
    /// 0-100 health index of the tiles.
    public let health: Int
    /// Ready / Degraded / Not available.
    public let readiness: String
    public let tiles: [DashboardTile]
    enum CodingKeys: String, CodingKey {
        case uuid, title, meta, latest, status, health, readiness, tiles
        case statusLabel = "status_label"
    }
}

public struct DashboardTile: Codable, Sendable {
    /// Saved tile id; null on the automatic board.
    public let uuid: String?
    /// What the tile shows: the custom label, else the point's default label.
    public let label: String
    /// The saved label; empty = default.
    public let customLabel: String
    public let pointId: Int?
    public let pointUuid: String
    public let assetId: Int?
    public let assetName: String
    public let transducerType: String
    /// Latest value of the point's default key, in ``unit``.
    public let value: Double?
    /// The viewer's unit (profile unit prefs), as the web shows.
    public let unit: String?
    public let decimals: Int
    public let measuredAt: String?
    /// An hour or more behind its section's ``latest``.
    public let lags: Bool
    /// 1 good, 2 elevated, 3 minor, 4 major.
    public let status: Int
    public let statusLabel: String
    /// Minor/Major and not stale: the only tiles the web colours.
    public let alarm: Bool
    /// Set when the MaintNode feed went silent.
    public let staleSince: String?
    /// State/Production points only.
    public let state: String?
    public let stateSince: String?
    /// Primary alarm limits, in ``unit``.
    public let limits: PointLimits?
    /// Today's trend; null for state points or no reading today.
    public let trend: DayTrend?
    /// Today's on/off intervals; state points only.
    public let timeline: [StateInterval]?
    enum CodingKeys: String, CodingKey {
        case uuid, label, value, unit, decimals, lags, status, alarm, state, limits, trend, timeline
        case customLabel = "custom_label", pointId = "point_id", pointUuid = "point_uuid", assetId = "asset_id"
        case assetName = "asset_name", transducerType = "transducer_type", measuredAt = "measured_at"
        case statusLabel = "status_label", staleSince = "stale_since", stateSince = "state_since"
    }
}

/// Today's trend (local 00:00 → 24:00, the web's TODAY strip), in the tile's unit. "Today" is the request's
/// timezone: the ``X-Timezone`` header (an IANA name such as ``Europe/Athens``; unknown names are ignored), else
/// the web's ``tz`` cookie, else UTC.
public struct DayTrend: Codable, Sendable {
    public let start: String
    public let end: String
    public let low: Double
    public let high: Double
    public let points: [TrendPoint]
    enum CodingKeys: String, CodingKey {
        case start, end, low, high, points
    }
}

public struct TrendPoint: Codable, Sendable {
    /// Start of the 15 min bin.
    public let t: String
    /// Mean of the bin's readings, in ``unit``.
    public let v: Double
    enum CodingKeys: String, CodingKey {
        case t, v
    }
}

public struct StateInterval: Codable, Sendable {
    public let start: String
    /// Null for the open interval: draw it to the client's now.
    public let end: String?
    public let isOn: Bool
    public let status: Int
    /// The still-running interval.
    public let isOpen: Bool
    enum CodingKeys: String, CodingKey {
        case start, end, status
        case isOn = "is_on", isOpen = "is_open"
    }
}

public struct DashboardSection: Codable, Sendable {
    public let uuid: String
    public let title: String
    public let position: Int
    enum CodingKeys: String, CodingKey {
        case uuid, title, position
    }
}

public struct DashboardTileRef: Codable, Sendable {
    public let uuid: String
    public let section: String
    public let pointId: Int?
    public let label: String
    public let customLabel: String
    public let position: Int
    enum CodingKeys: String, CodingKey {
        case uuid, section, label, position
        case pointId = "point_id", customLabel = "custom_label"
    }
}
