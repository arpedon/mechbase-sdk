import Foundation

public struct Routes: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    public func list(query: String? = nil, limit: Int = 50, offset: Int = 0) async throws -> [Route] {
        let q: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        let page = try await scope.http.get(scope.path("/routes"), query: q, as: Page<Route>.self)
        return page.items
    }

    /// Fetch the ordered detail (items) for a route.
    public func detail(routeUUID: String) async throws -> RouteDetail {
        try await scope.http.get(scope.path("/routes/\(routeUUID)"), as: RouteDetail.self)
    }

    /// Start a new execution of a route.
    ///
    /// Online callers pass only `routeUUID` and the server mints the execution
    /// uuid. Offline-first clients mint the uuid locally and pass `uuid` (plus the
    /// real field `startedAt`) so a queued, later-pushed start lands
    /// deterministically; the server upserts on uuid, so a retried push is
    /// idempotent. Both are optional — a bare call is the legacy empty POST.
    public func start(routeUUID: String, uuid: String? = nil, startedAt: Date? = nil) async throws -> Execution {
        let path = scope.path("/routes/\(routeUUID)/executions")
        if uuid == nil && startedAt == nil {
            let exec = try await scope.http.post(path, as: RouteExecution.self)
            return Execution(scope: scope, execution: exec)
        }
        struct StartBody: Encodable {
            let uuid: String?
            let started_at: Date?
        }
        let exec = try await scope.http.postJSON(
            path,
            body: StartBody(uuid: uuid, started_at: startedAt),
            as: RouteExecution.self
        )
        return Execution(scope: scope, execution: exec)
    }

    /// Re-attach to an existing execution by UUID without making a request.
    public func execution(uuid: String, routeUUID: String = "", sessionId: String = "") -> Execution {
        let exec = RouteExecution(
            uuid: uuid,
            routeUuid: routeUUID,
            status: "in_progress",
            startedAt: nil,
            completedAt: nil,
            sessionId: sessionId
        )
        return Execution(scope: scope, execution: exec)
    }
}

