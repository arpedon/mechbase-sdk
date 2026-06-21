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
    public func start(routeUUID: String) async throws -> Execution {
        let exec = try await scope.http.post(
            scope.path("/routes/\(routeUUID)/executions"),
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

