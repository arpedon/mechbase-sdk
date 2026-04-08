import Foundation

/// Top-level Mechbase client.
///
/// ```swift
/// let client = MechbaseClient(token: "...")  // defaults to https://app.mechbase.io
/// let me = try await client.me()
/// let installation = client.forInstallation(id: me.currentInstallationId)
/// ```
///
/// For self-hosted installations, pass an explicit `baseURL`.
public final class MechbaseClient: Sendable {
    /// Default base URL for the hosted Mechbase service.
    public static let defaultBaseURL: URL = URL(string: "https://app.mechbase.io")!

    let http: HTTPClient

    public init(token: String, baseURL: URL = MechbaseClient.defaultBaseURL, session: URLSession = .shared) {
        self.http = HTTPClient(baseURL: baseURL, token: token, session: session)
    }

    /// Fetch the current user, their installations, and the active installation id.
    public func me() async throws -> Me {
        try await http.get("/api/me/", as: Me.self)
    }

    /// Return a handle bound to a specific installation.
    public func forInstallation(id: Int) -> Installation {
        Installation(http: http, installationId: id)
    }
}
