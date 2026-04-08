import Foundation

public struct Assets: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    /// List assets for the installation.
    public func list(
        query: String? = nil,
        zoneId: Int? = nil,
        limit: Int = 50,
        offset: Int = 0
    ) async throws -> [Asset] {
        let q: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "zone_id", value: zoneId.map(String.init)),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        let page = try await scope.http.get(scope.path("/assets"), query: q, as: Page<Asset>.self)
        return page.items
    }

    /// Fetch a single asset by id.
    public func get(id: Int) async throws -> Asset {
        try await scope.http.get(scope.path("/assets/\(id)"), as: Asset.self)
    }
}
