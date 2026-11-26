import Foundation

/// All resources scoped to a single installation.
public final class Installation: Sendable {
    public let installationId: Int
    public let assets: Assets
    public let measurementPoints: MeasurementPoints
    public let measurements: Measurements
    public let routes: Routes
    public let sections: Sections
    public let zones: Zones
    public let findings: Findings
    public let exports: Exports
    private let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
        self.installationId = installationId
        self.assets = Assets(http: http, installationId: installationId)
        self.measurementPoints = MeasurementPoints(http: http, installationId: installationId)
        self.measurements = Measurements(http: http, installationId: installationId)
        self.routes = Routes(http: http, installationId: installationId)
        self.sections = Sections(http: http, installationId: installationId)
        self.zones = Zones(http: http, installationId: installationId)
        self.findings = Findings(http: http, installationId: installationId)
        self.exports = Exports(http: http, installationId: installationId)
    }

    private struct LegacyRedirectsPage: Decodable { let items: [LegacyRedirect] }

    /// The legacy v1 QR URL → v2 measurement point map, for resolving old QR
    /// tags offline. Fetch once per sync and cache it.
    public func legacyRedirects() async throws -> [LegacyRedirect] {
        try await scope.http.get(scope.path("/legacy-redirects"), as: LegacyRedirectsPage.self).items
    }
}

/// One legacy QR mapping: a v1 `/plantlayer|measurementpoint/<uuid>/` URL and
/// the v2 measurement point it now is.
public struct LegacyRedirect: Codable, Sendable, Equatable {
    public let legacyUrl: String
    public let mpUuid: String
    public let mpPath: String
    public let installationId: Int
    public let assetId: Int?
    public let pointId: Int?

    enum CodingKeys: String, CodingKey {
        case legacyUrl = "legacy_url", mpUuid = "mp_uuid", mpPath = "mp_path"
        case installationId = "installation_id", assetId = "asset_id", pointId = "point_id"
    }
}

/// Internal helper for building installation-scoped paths.
struct InstallationScope: Sendable {
    let http: HTTPClient
    let installationId: Int

    func path(_ suffix: String) -> String {
        "/api/installations/\(installationId)\(suffix)"
    }
}
