import Foundation

/// All resources scoped to a single installation.
public final class Installation: Sendable {
    public let installationId: Int
    public let assets: Assets
    public let measurementPoints: MeasurementPoints
    public let measurements: Measurements
    public let routes: Routes

    init(http: HTTPClient, installationId: Int) {
        self.installationId = installationId
        self.assets = Assets(http: http, installationId: installationId)
        self.measurementPoints = MeasurementPoints(http: http, installationId: installationId)
        self.measurements = Measurements(http: http, installationId: installationId)
        self.routes = Routes(http: http, installationId: installationId)
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
