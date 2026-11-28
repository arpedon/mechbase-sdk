import Foundation

// Record a finding from a spectrum cursor, its choices, and the bearing library.

/// Where the analyst clicked a spectrum, for ``Findings/create(_:)`` and ``Findings/choices(pointId:pointSequence:cursor:)``.
public struct SpectrumCursor: Sendable {
    /// Frequency, Hz.
    public var hz: Double?
    /// Amplitude, in `unit`.
    public var amplitude: Double?
    public var unit: String
    /// "" | accel | velocity | envelope.
    public var signal: String
    /// The 1x the chart drew; the reading's own when nil.
    public var shaftHz: Double?
    /// The spectrum's line spacing, Hz: pass ``Vibration/sourceResolutionHz``.
    public var df: Double?

    public init(hz: Double? = nil, amplitude: Double? = nil, unit: String = "", signal: String = "",
                shaftHz: Double? = nil, df: Double? = nil) {
        self.hz = hz; self.amplitude = amplitude; self.unit = unit; self.signal = signal
        self.shaftHz = shaftHz; self.df = df
    }
}

/// A finding on a reading, as the web's Record finding dialog makes it.
public struct FindingInput: Encodable, Sendable {
    public var pointId: Int
    public var pointSequence: Int
    /// A ``FindingChoices/faultTypes`` value.
    public var faultType: String
    /// A ``FindingChoices/severities`` value.
    public var severity: String
    public var recommendedAction: String
    /// `YYYY-MM-DD`.
    public var dueBy: String?
    public var comment: String
    public var cursor: SpectrumCursor

    public init(pointId: Int, pointSequence: Int, faultType: String, severity: String, recommendedAction: String = "",
                dueBy: String? = nil, comment: String = "", cursor: SpectrumCursor = SpectrumCursor()) {
        self.pointId = pointId; self.pointSequence = pointSequence; self.faultType = faultType
        self.severity = severity; self.recommendedAction = recommendedAction; self.dueBy = dueBy
        self.comment = comment; self.cursor = cursor
    }

    enum CodingKeys: String, CodingKey {
        case severity, comment, hz, amplitude, unit, signal, df
        case pointId = "point_id", pointSequence = "point_sequence", faultType = "fault_type"
        case recommendedAction = "recommended_action", dueBy = "due_by", shaftHz = "shaft_hz"
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(pointId, forKey: .pointId)
        try c.encode(pointSequence, forKey: .pointSequence)
        try c.encode(faultType, forKey: .faultType)
        try c.encode(severity, forKey: .severity)
        try c.encode(recommendedAction, forKey: .recommendedAction)
        try c.encodeIfPresent(dueBy, forKey: .dueBy)
        try c.encode(comment, forKey: .comment)
        try c.encodeIfPresent(cursor.hz, forKey: .hz)
        try c.encodeIfPresent(cursor.amplitude, forKey: .amplitude)
        try c.encode(cursor.unit, forKey: .unit)
        try c.encode(cursor.signal, forKey: .signal)
        try c.encodeIfPresent(cursor.shaftHz, forKey: .shaftHz)
        try c.encodeIfPresent(cursor.df, forKey: .df)
    }
}

extension Findings {
    /// Record a finding (also a note on the asset's thread); the server derives the evidence from the cursor.
    public func create(_ input: FindingInput) async throws -> Finding {
        try await scope.http.postJSON(scope.path("/findings/"), body: input, as: Finding.self)
    }

    /// Fault types and severities. With a reading (and cursor), also the evidence the server would
    /// store and the fault type the cursor's bearing-marker match suggests.
    public func choices(pointId: Int? = nil, pointSequence: Int? = nil,
                        cursor: SpectrumCursor = SpectrumCursor()) async throws -> FindingChoices {
        let q = [
            URLQueryItem(name: "point_id", value: pointId.map(String.init)),
            URLQueryItem(name: "point_sequence", value: pointSequence.map(String.init)),
            URLQueryItem(name: "hz", value: cursor.hz.map { String($0) }),
            URLQueryItem(name: "amplitude", value: cursor.amplitude.map { String($0) }),
            URLQueryItem(name: "unit", value: cursor.unit),
            URLQueryItem(name: "signal", value: cursor.signal),
            URLQueryItem(name: "shaft_hz", value: cursor.shaftHz.map { String($0) }),
            URLQueryItem(name: "df", value: cursor.df.map { String($0) }),
        ]
        return try await scope.http.get(scope.path("/findings/choices/"), query: q, as: FindingChoices.self)
    }
}

/// A custom bearing: all four defect orders, or none and the geometry to derive them. Nil fields
/// are not sent (on PATCH they keep their value; new geometry without orders re-derives the orders).
public struct BearingInput: Encodable, Sendable {
    /// Required to create.
    public var designation: String?
    public var manufacturer: String?
    public var rollingElements: Int?
    public var bpfo: Double?
    public var bpfi: Double?
    public var bsf: Double?
    public var ftf: Double?
    public var ballDiameter: Double?
    public var pitchDiameter: Double?
    public var contactAngle: Double?

    public init(designation: String? = nil, manufacturer: String? = nil, rollingElements: Int? = nil,
                bpfo: Double? = nil, bpfi: Double? = nil, bsf: Double? = nil, ftf: Double? = nil,
                ballDiameter: Double? = nil, pitchDiameter: Double? = nil, contactAngle: Double? = nil) {
        self.designation = designation; self.manufacturer = manufacturer; self.rollingElements = rollingElements
        self.bpfo = bpfo; self.bpfi = bpfi; self.bsf = bsf; self.ftf = ftf
        self.ballDiameter = ballDiameter; self.pitchDiameter = pitchDiameter; self.contactAngle = contactAngle
    }

    enum CodingKeys: String, CodingKey {
        case designation, manufacturer, bpfo, bpfi, bsf, ftf
        case rollingElements = "rolling_elements", ballDiameter = "ball_diameter"
        case pitchDiameter = "pitch_diameter", contactAngle = "contact_angle"
    }
}

/// The installation's own bearings plus the shared (read-only) library.
public final class Bearings: Sendable {
    private let scope: InstallationScope
    init(http: HTTPClient, installationId: Int) { scope = InstallationScope(http: http, installationId: installationId) }

    private func path(_ uuid: String) throws -> String {
        try requireUUID(uuid)
        return scope.path("/bearings/\(uuid)")
    }

    /// `own` always; `results` searches by designation/manufacturer with `query` (≥ 2 characters, ≤ 100
    /// hits), or with `order` (0 < order < 100) matches a detected tone (≤ 8; `sideband` "1x" or "ftf").
    public func list(query: String = "", order: Double? = nil, sideband: String? = nil) async throws -> BearingList {
        let q = [URLQueryItem(name: "q", value: query),
                 URLQueryItem(name: "order", value: order.map { String($0) }),
                 URLQueryItem(name: "sideband", value: sideband)]
        return try await scope.http.get(scope.path("/bearings"), query: q, as: BearingList.self)
    }

    public func get(uuid: String) async throws -> Bearing {
        try await scope.http.get(try path(uuid), as: Bearing.self)
    }

    public func create(_ input: BearingInput) async throws -> Bearing {
        try await scope.http.postJSON(scope.path("/bearings"), body: input, as: Bearing.self)
    }

    /// Own bearings only (a library one is 404).
    public func update(uuid: String, _ input: BearingInput) async throws -> Bearing {
        try await scope.http.patchJSON(try path(uuid), body: input, as: Bearing.self)
    }

    /// Its points lose the bearing. Library bearings 404.
    public func delete(uuid: String) async throws {
        _ = try await scope.http.delete(try path(uuid), as: EmptyResponse.self)
    }
}

public struct FindingChoices: Codable, Sendable {
    public let faultTypes: [Choice]
    public let severities: [Choice]
    public let suggestedFaultType: String?
    public let evidence: JSONValue
    enum CodingKeys: String, CodingKey {
        case severities, evidence
        case faultTypes = "fault_types", suggestedFaultType = "suggested_fault_type"
    }
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.faultTypes = try c.decode([Choice].self, forKey: .faultTypes)
        self.severities = try c.decode([Choice].self, forKey: .severities)
        self.suggestedFaultType = try c.decodeIfPresent(String.self, forKey: .suggestedFaultType)
        self.evidence = try c.decodeIfPresent(JSONValue.self, forKey: .evidence) ?? .object([:])
    }
}

public struct Choice: Codable, Sendable {
    public let value: String
    public let label: String
    enum CodingKeys: String, CodingKey {
        case value, label
    }
}

public struct BearingList: Codable, Sendable {
    public let own: [Bearing]
    public let results: [Bearing]
    public let libraryCount: Int
    enum CodingKeys: String, CodingKey {
        case own, results
        case libraryCount = "library_count"
    }
}

public struct Bearing: Codable, Sendable {
    public let uuid: String
    public let designation: String
    public let manufacturer: String
    /// "library" (shared, read-only) or "custom" (this installation's own).
    public let source: String
    public let editable: Bool
    public let rollingElements: Int?
    public let bpfo: Double
    public let bpfi: Double
    public let bsf: Double
    public let ftf: Double
    public let ballDiameter: Double?
    public let pitchDiameter: Double?
    public let contactAngle: Double?
    /// Points fitted with it; own bearings in the list only.
    public let pointCount: Int?
    /// With ?order=: which defect order matched ("BPFO", "2xBSF", …).
    public let match: String?
    enum CodingKeys: String, CodingKey {
        case uuid, designation, manufacturer, source, editable, bpfo, bpfi, bsf, ftf, match
        case rollingElements = "rolling_elements", ballDiameter = "ball_diameter"
        case pitchDiameter = "pitch_diameter", contactAngle = "contact_angle", pointCount = "point_count"
    }
}
