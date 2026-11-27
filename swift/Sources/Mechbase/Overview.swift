import Foundation

// Home tab: overview, alerts, activity, search, running hours, production flip, notification settings.

extension Installation {
    private var http: HTTPClient { scope.http }

    /// What the web home shows: status summary, the top 6 needs-attention rows
    /// (`attentionMoreCount` more are on ``alerts(silentOnly:)``), runs in progress, back to normal.
    public func overview() async throws -> Overview {
        try await http.get(scope.path("/overview"), as: Overview.self)
    }

    /// Non-Normal assets worst first, then silent ones; `silentOnly` lists every silent asset instead.
    public func alerts(silentOnly: Bool = false) async throws -> [AssetAlert] {
        try await http.get(scope.path("/alerts"), query: [URLQueryItem(name: "show", value: silentOnly ? "silent" : nil)],
                           as: [AssetAlert].self)
    }

    /// One page of the activity feed, newest first (`limit` ≤ 200). Pass `nextCursor` back as `cursor`.
    /// Group by local day client-side. `assetId` narrows it to one asset (status changes, notes,
    /// findings and the route runs that checked it).
    public func activity(cursor: String? = nil, limit: Int = 50, sectionId: Int? = nil,
                         assetId: Int? = nil) async throws -> ActivityPage {
        let q = [
            URLQueryItem(name: "cursor", value: cursor),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "section_id", value: sectionId.map(String.init)),
            URLQueryItem(name: "asset_id", value: assetId.map(String.init)),
        ]
        return try await http.get(scope.path("/activity"), query: q, as: ActivityPage.self)
    }

    /// The whole activity feed, newest first, following cursors until it ends or the task is cancelled.
    public func activityFeed(pageSize: Int = 50, sectionId: Int? = nil,
                             assetId: Int? = nil) -> AsyncThrowingStream<ActivityEntry, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                var cursor: String?
                do {
                    repeat {
                        let page = try await activity(cursor: cursor, limit: pageSize, sectionId: sectionId, assetId: assetId)
                        for entry in page.items { continuation.yield(entry) }
                        cursor = page.nextCursor
                    } while cursor?.isEmpty == false && !Task.isCancelled
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    /// Search the installation. `query` under 2 characters finds nothing. `category` (a
    /// ``SearchCategory/slug``) fills only that list, with more rows.
    public func search(_ query: String, category: String? = nil) async throws -> SearchResults {
        try await http.get(scope.path("/search"), query: [URLQueryItem(name: "q", value: query),
                                                          URLQueryItem(name: "in", value: category)],
                           as: SearchResults.self)
    }

    /// Running hours over local days (ISO dates, `YYYY-MM-DD`). Neither: today.
    public func hours(from: String? = nil, to: String? = nil) async throws -> RunningHours {
        try await http.get(scope.path("/hours"), query: [URLQueryItem(name: "production_from", value: from),
                                                         URLQueryItem(name: "production_to", value: to)],
                           as: RunningHours.self)
    }

    public func notificationSettings() async throws -> NotificationSettings {
        try await http.get(scope.path("/notification-settings"), as: NotificationSettings.self)
    }

    /// Fields left nil keep their value. `notificationsMuted` is account-wide.
    public func updateNotificationSettings(_ input: NotificationSettingsInput) async throws -> NotificationSettings {
        try await http.patchJSON(scope.path("/notification-settings"), body: input, as: NotificationSettings.self)
    }

    /// Sends a test email at once, muted or not. 422 without an email address; 502 when the provider refused it.
    public func sendTestNotificationEmail() async throws -> EmailTestResult {
        try await http.post(scope.path("/notification-settings/test"), as: EmailTestResult.self)
    }
}

extension Assets {
    /// Flip the asset's production (on/off) state; returns the new state.
    public func flipProduction(assetId: Int) async throws -> ProductionState {
        try await scope.http.post(scope.path("/assets/\(assetId)/production/flip"), as: ProductionState.self)
    }
}

/// Partial notification-settings update: nil fields are not sent.
public struct NotificationSettingsInput: Encodable, Sendable {
    /// A ``ThresholdChoice/value``.
    public var severityThreshold: Int?
    public var statusChanges: Bool?
    public var routeCompletions: Bool?
    public var exports: Bool?
    public var notificationsMuted: Bool?

    public init(severityThreshold: Int? = nil, statusChanges: Bool? = nil, routeCompletions: Bool? = nil,
                exports: Bool? = nil, notificationsMuted: Bool? = nil) {
        self.severityThreshold = severityThreshold
        self.statusChanges = statusChanges
        self.routeCompletions = routeCompletions
        self.exports = exports
        self.notificationsMuted = notificationsMuted
    }

    enum CodingKeys: String, CodingKey {
        case exports
        case severityThreshold = "severity_threshold", statusChanges = "status_changes"
        case routeCompletions = "route_completions", notificationsMuted = "notifications_muted"
    }
}

public struct Overview: Codable, Sendable {
    public let statusSummary: StatusSummary
    public let briefing: Briefing
    public let lastReadingAt: String?
    public let attention: [AssetAlert]
    public let attentionMoreCount: Int
    public let silentCount: Int
    public let runningExecutions: [RunningExecution]
    public let routes: [RouteSummary]
    public let backToNormal: [BackToNormal]
    public let sections: [SectionStatus]
    enum CodingKeys: String, CodingKey {
        case briefing, attention, routes, sections
        case statusSummary = "status_summary", lastReadingAt = "last_reading_at"
        case attentionMoreCount = "attention_more_count", silentCount = "silent_count"
        case runningExecutions = "running_executions", backToNormal = "back_to_normal"
    }
}

public struct StatusSummary: Codable, Sendable {
    public let total: Int
    public let nominal: Int
    public let elevated: Int
    public let warning: Int
    public let critical: Int
    public let attention: Int
    enum CodingKeys: String, CodingKey {
        case total, nominal, elevated, warning, critical, attention
    }
}

public struct Briefing: Codable, Sendable {
    public let critical: Int
    public let warning: Int
    public let check: Int
    public let silent: Int
    public let silentSince: String?
    public let normal: Int
    public let attention: Int
    public let lastReading: String?
    enum CodingKeys: String, CodingKey {
        case critical, warning, check, silent, normal, attention
        case silentSince = "silent_since", lastReading = "last_reading"
    }
}

/// One needs-attention row: a non-Normal asset, or a silent one.
public struct AssetAlert: Codable, Sendable {
    public let sectionId: Int?
    public let sectionName: String
    public let zoneId: Int?
    public let zoneName: String?
    public let assetId: Int?
    public let assetUuid: String
    public let name: String
    public let status: Int
    public let isSilent: Bool
    public let reason: String
    public let triggerName: String
    public let triggerPointId: Int?
    public let triggerRoute: String
    public let silentPoints: [String]
    public let alertSince: String?
    enum CodingKeys: String, CodingKey {
        case name, status, reason
        case sectionId = "section_id", sectionName = "section_name", zoneId = "zone_id", zoneName = "zone_name"
        case assetId = "asset_id", assetUuid = "asset_uuid", isSilent = "is_silent", triggerName = "trigger_name"
        case triggerPointId = "trigger_point_id", triggerRoute = "trigger_route", silentPoints = "silent_points"
        case alertSince = "alert_since"
    }
}

public struct RunningExecution: Codable, Sendable {
    public let executionUuid: String
    public let routeUuid: String
    public let routeName: String
    public let startedAt: String?
    public let executedBy: PersonRef?
    public let done: Int
    public let total: Int
    public let lastCompletedExecutionUuid: String?
    enum CodingKeys: String, CodingKey {
        case done, total
        case executionUuid = "execution_uuid", routeUuid = "route_uuid", routeName = "route_name"
        case startedAt = "started_at", executedBy = "executed_by"
        case lastCompletedExecutionUuid = "last_completed_execution_uuid"
    }
}

public struct RouteSummary: Codable, Sendable {
    public let routeUuid: String
    public let name: String
    public let itemCount: Int
    public let lastRun: LastRun?
    enum CodingKeys: String, CodingKey {
        case name
        case routeUuid = "route_uuid", itemCount = "item_count", lastRun = "last_run"
    }
}

public struct LastRun: Codable, Sendable {
    public let executionUuid: String
    public let startedAt: String?
    public let completedAt: String?
    public let failCount: Int
    enum CodingKeys: String, CodingKey {
        case executionUuid = "execution_uuid", startedAt = "started_at", completedAt = "completed_at"
        case failCount = "fail_count"
    }
}

public struct BackToNormal: Codable, Sendable {
    public let sectionId: Int?
    public let sectionName: String
    public let zoneId: Int?
    public let zoneName: String?
    public let assetId: Int?
    public let assetUuid: String
    public let name: String
    public let recoveredAt: String
    public let reason: String
    enum CodingKeys: String, CodingKey {
        case name, reason
        case sectionId = "section_id", sectionName = "section_name", zoneId = "zone_id", zoneName = "zone_name"
        case assetId = "asset_id", assetUuid = "asset_uuid", recoveredAt = "recovered_at"
    }
}

public struct SectionStatus: Codable, Sendable {
    public let sectionId: Int?
    public let uuid: String
    public let name: String
    public let assetCount: Int
    public let checkCount: Int
    public let warningCount: Int
    public let criticalCount: Int
    public let worstStatus: Int?
    enum CodingKeys: String, CodingKey {
        case uuid, name
        case sectionId = "section_id", assetCount = "asset_count", checkCount = "check_count"
        case warningCount = "warning_count", criticalCount = "critical_count", worstStatus = "worst_status"
    }
}

public struct PersonRef: Codable, Sendable {
    public let id: Int
    public let name: String
    enum CodingKeys: String, CodingKey {
        case id, name
    }
}

public struct ActivityEntry: Codable, Sendable {
    public let kind: String
    public let timestamp: String
    public let title: String
    public let detail: String
    public let state: String
    public let severity: Int
    public let actor: PersonRef?
    public let oldStatus: Int?
    public let newStatus: Int?
    public let assetId: Int?
    public let pointId: Int?
    public let commentId: Int?
    public let findingUuid: String?
    public let executionUuid: String?
    public let routeUuid: String?
    enum CodingKeys: String, CodingKey {
        case kind, timestamp, title, detail, state, severity, actor
        case oldStatus = "old_status", newStatus = "new_status", assetId = "asset_id", pointId = "point_id"
        case commentId = "comment_id", findingUuid = "finding_uuid", executionUuid = "execution_uuid"
        case routeUuid = "route_uuid"
    }
}

public struct ActivityPage: Codable, Sendable {
    public let items: [ActivityEntry]
    public let nextCursor: String?
    enum CodingKeys: String, CodingKey {
        case items
        case nextCursor = "next_cursor"
    }
}

public struct SearchResults: Codable, Sendable {
    public let query: String
    public let category: String?
    public let totalCount: Int
    public let categories: [SearchCategory]
    public let assets: [SearchAsset]
    public let sections: [SearchSection]
    public let zones: [SearchZone]
    public let points: [SearchPoint]
    public let routes: [SearchRoute]
    public let routeItems: [SearchRouteItem]
    public let comments: [SearchComment]
    public let itemResponses: [SearchNote]
    enum CodingKeys: String, CodingKey {
        case query, category, categories, assets, sections, zones, points, routes, comments
        case totalCount = "total_count", routeItems = "route_items", itemResponses = "item_responses"
    }
}

public struct SearchCategory: Codable, Sendable {
    public let key: String
    public let slug: String
    public let label: String
    public let count: Int
    public let selected: Bool
    enum CodingKeys: String, CodingKey {
        case key, slug, label, count, selected
    }
}

public struct SearchAsset: Codable, Sendable {
    public let sectionId: Int?
    public let sectionName: String
    public let zoneId: Int?
    public let zoneName: String?
    public let assetId: Int?
    public let uuid: String
    public let name: String
    public let status: Int
    enum CodingKeys: String, CodingKey {
        case uuid, name, status
        case sectionId = "section_id", sectionName = "section_name", zoneId = "zone_id", zoneName = "zone_name"
        case assetId = "asset_id"
    }
}

public struct SearchSection: Codable, Sendable {
    public let sectionId: Int?
    public let uuid: String
    public let name: String
    enum CodingKeys: String, CodingKey {
        case uuid, name
        case sectionId = "section_id"
    }
}

public struct SearchZone: Codable, Sendable {
    public let zoneId: Int?
    public let uuid: String
    public let name: String
    public let alias: String
    public let sectionId: Int?
    public let sectionName: String
    enum CodingKeys: String, CodingKey {
        case uuid, name, alias
        case zoneId = "zone_id", sectionId = "section_id", sectionName = "section_name"
    }
}

public struct SearchPoint: Codable, Sendable {
    public let pointId: Int?
    public let uuid: String
    public let name: String
    public let location: String
    public let transducerType: String
    public let transducerTypeLabel: String
    public let status: Int
    public let assetId: Int?
    public let assetName: String
    public let sectionName: String
    enum CodingKeys: String, CodingKey {
        case uuid, name, location, status
        case pointId = "point_id", transducerType = "transducer_type"
        case transducerTypeLabel = "transducer_type_label", assetId = "asset_id", assetName = "asset_name"
        case sectionName = "section_name"
    }
}

public struct SearchRoute: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let description: String
    enum CodingKeys: String, CodingKey {
        case uuid, name, description
    }
}

public struct SearchRouteItem: Codable, Sendable {
    public let uuid: String
    public let checkId: Int?
    public let label: String
    public let routeUuid: String
    public let routeName: String
    public let assetId: Int?
    public let assetName: String?
    enum CodingKeys: String, CodingKey {
        case uuid, label
        case checkId = "check_id", routeUuid = "route_uuid", routeName = "route_name", assetId = "asset_id"
        case assetName = "asset_name"
    }
}

public struct SearchComment: Codable, Sendable {
    public let commentId: Int
    public let bodyText: String
    public let authorName: String
    public let createdAt: String
    public let assetId: Int?
    public let assetName: String
    enum CodingKeys: String, CodingKey {
        case commentId = "comment_id", bodyText = "body_text", authorName = "author_name"
        case createdAt = "created_at", assetId = "asset_id", assetName = "asset_name"
    }
}

public struct SearchNote: Codable, Sendable {
    public let responseUuid: String
    public let notes: String
    public let executionUuid: String
    public let routeUuid: String
    public let routeName: String
    public let startedAt: String?
    public let assetId: Int?
    public let assetName: String?
    enum CodingKeys: String, CodingKey {
        case notes
        case responseUuid = "response_uuid", executionUuid = "execution_uuid", routeUuid = "route_uuid"
        case routeName = "route_name", startedAt = "started_at", assetId = "asset_id", assetName = "asset_name"
    }
}

public struct RunningHours: Codable, Sendable {
    public let productionFrom: String?
    public let productionTo: String?
    public let windowStart: String
    public let windowEnd: String
    public let staleHours: Int
    public let rows: [RunningHoursRow]
    enum CodingKeys: String, CodingKey {
        case rows
        case productionFrom = "production_from", productionTo = "production_to", windowStart = "window_start"
        case windowEnd = "window_end", staleHours = "stale_hours"
    }
}

public struct RunningHoursRow: Codable, Sendable {
    public let state: String?
    public let lastPing: String?
    public let sectionId: Int?
    public let sectionName: String
    public let zoneId: Int?
    public let zoneName: String?
    public let assetId: Int?
    public let assetUuid: String
    public let assetName: String
    public let pointId: Int?
    public let rangeHours: Double
    public let lifetimeHours: Double
    public let segments: [HoursSegment]
    enum CodingKeys: String, CodingKey {
        case state, segments
        case lastPing = "last_ping", sectionId = "section_id", sectionName = "section_name", zoneId = "zone_id"
        case zoneName = "zone_name", assetId = "asset_id", assetUuid = "asset_uuid", assetName = "asset_name"
        case pointId = "point_id", rangeHours = "range_hours", lifetimeHours = "lifetime_hours"
    }
}

public struct HoursSegment: Codable, Sendable {
    public let startPct: Double
    public let widthPct: Double
    enum CodingKeys: String, CodingKey {
        case startPct = "start_pct", widthPct = "width_pct"
    }
}

public struct ProductionState: Codable, Sendable {
    public let state: String?
    public let lastPing: String?
    enum CodingKeys: String, CodingKey {
        case state
        case lastPing = "last_ping"
    }
}

public struct NotificationSettings: Codable, Sendable {
    public let severityThreshold: Int
    public let statusChanges: Bool
    public let routeCompletions: Bool
    public let exports: Bool
    public let notificationsMuted: Bool
    public let thresholdChoices: [ThresholdChoice]
    enum CodingKeys: String, CodingKey {
        case exports
        case severityThreshold = "severity_threshold", statusChanges = "status_changes"
        case routeCompletions = "route_completions", notificationsMuted = "notifications_muted"
        case thresholdChoices = "threshold_choices"
    }
}

public struct ThresholdChoice: Codable, Sendable {
    public let value: Int
    public let label: String
    enum CodingKeys: String, CodingKey {
        case value, label
    }
}

public struct EmailTestResult: Codable, Sendable {
    public let result: String
    enum CodingKeys: String, CodingKey {
        case result
    }
}
