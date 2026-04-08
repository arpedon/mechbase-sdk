import Foundation

public struct MeasurementPoints: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    public func list(
        query: String? = nil,
        assetId: Int? = nil,
        transducerType: String? = nil,
        limit: Int = 50,
        offset: Int = 0
    ) async throws -> [MeasurementPoint] {
        let q: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "asset_id", value: assetId.map(String.init)),
            URLQueryItem(name: "transducer_type", value: transducerType),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        let page = try await scope.http.get(
            scope.path("/measurement-points"),
            query: q,
            as: Page<MeasurementPoint>.self
        )
        return page.items
    }

    public func get(id: Int) async throws -> MeasurementPoint {
        try await scope.http.get(scope.path("/measurement-points/\(id)"), as: MeasurementPoint.self)
    }
}
