import Foundation

/// Partial profile update for ``MechbaseClient/updateMe(_:)``: nil fields are not sent
/// (an explicit null is a 422 server-side; send "" to clear a name).
public struct MeInput: Encodable, Sendable {
    public var firstName: String?
    public var lastName: String?
    public var unitPrefs: UnitPrefsInput?

    public init(firstName: String? = nil, lastName: String? = nil, unitPrefs: UnitPrefsInput? = nil) {
        self.firstName = firstName
        self.lastName = lastName
        self.unitPrefs = unitPrefs
    }

    enum CodingKeys: String, CodingKey {
        case firstName = "first_name", lastName = "last_name", unitPrefs = "unit_prefs"
    }
}

/// Display units to change (e.g. `velocity: "in/s"`); nil keeps the current choice.
public struct UnitPrefsInput: Encodable, Sendable {
    public var acceleration: String?
    public var velocity: String?
    public var temperature: String?
    public var pressure: String?
    public var frequency: String?

    public init(acceleration: String? = nil, velocity: String? = nil, temperature: String? = nil,
                pressure: String? = nil, frequency: String? = nil) {
        self.acceleration = acceleration
        self.velocity = velocity
        self.temperature = temperature
        self.pressure = pressure
        self.frequency = frequency
    }
}

extension MechbaseClient {
    /// Update the profile's name and display units, validated as the web profile form; returns the new `/me`.
    public func updateMe(_ input: MeInput) async throws -> Me {
        try await http.patchJSON("/api/me/", body: input, as: Me.self)
    }
}

/// A one-time browser sign-in link from ``MechbaseClient/webSession(next:)``.
public struct WebSession: Codable, Sendable {
    /// Open within the minute, once: it signs the browser in as this token's user and lands on `next`.
    public let url: URL
    public let expiresAt: String
    enum CodingKeys: String, CodingKey { case url; case expiresAt = "expires_at" }
}

extension MechbaseClient {
    private struct WebSessionBody: Encodable { let next: String }

    /// A single-use, 60-second link that signs an in-app browser in and opens `next`, so a web page
    /// doesn't ask the technician to log in again. `next` is a path on the server ("/2012/assets/5/")
    /// or the `https://` URL of a device tunnel the user can open; anything else is
    /// ``MechbaseError/validation(_:)``. A service or installation-scoped token gets 403.
    /// Mint it right before opening it, never cache it.
    public func webSession(next: String) async throws -> WebSession {
        try await http.postJSON("/api/auth/web-session", body: WebSessionBody(next: next), as: WebSession.self)
    }
}
