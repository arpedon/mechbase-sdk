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
