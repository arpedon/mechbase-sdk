import Foundation
import CoreFoundation

/// A heterogeneous JSON value used for free-form `data` fields and request payloads.
public enum JSONValue: Codable, Equatable, Sendable {
    case null
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null; return }
        if let v = try? c.decode(Bool.self) { self = .bool(v); return }
        if let v = try? c.decode(Int.self) { self = .int(v); return }
        if let v = try? c.decode(Double.self) { self = .double(v); return }
        if let v = try? c.decode(String.self) { self = .string(v); return }
        if let v = try? c.decode([JSONValue].self) { self = .array(v); return }
        if let v = try? c.decode([String: JSONValue].self) { self = .object(v); return }
        throw DecodingError.dataCorruptedError(in: c, debugDescription: "Unknown JSON value")
    }

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .null: try c.encodeNil()
        case .bool(let v): try c.encode(v)
        case .int(let v): try c.encode(v)
        case .double(let v): try c.encode(v)
        case .string(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .object(let v): try c.encode(v)
        }
    }
}

public extension JSONValue {
    /// Convenience: build a JSON object from a Swift dictionary of basic values.
    static func from(_ dict: [String: Any]) -> JSONValue {
        var out: [String: JSONValue] = [:]
        for (k, v) in dict { out[k] = wrap(v) }
        return .object(out)
    }

    private static func wrap(_ v: Any) -> JSONValue {
        // `JSONSerialization` represents JSON numbers AND booleans as `NSNumber`.
        // A numeric `NSNumber` whose value is 0 or 1 will *also* satisfy
        // `as? Bool` (NSNumber(1) as? Bool == true), so a plain `case let b as
        // Bool` first would silently coerce a measurement of 0/1 into a boolean
        // — corrupting the value and disabling server-side alarm evaluation
        // (Decimal(str(True)) throws -> GOOD). Disambiguate genuine booleans
        // from numbers by the CoreFoundation type id BEFORE the bridging casts.
        if let num = v as? NSNumber {
            if CFGetTypeID(num) == CFBooleanGetTypeID() { return .bool(num.boolValue) }
            // Integer-valued numbers stay ints; everything else is a double.
            if CFNumberIsFloatType(num) { return .double(num.doubleValue) }
            return .int(num.intValue)
        }
        switch v {
        case is NSNull: return .null
        case let b as Bool: return .bool(b)
        case let i as Int: return .int(i)
        case let d as Double: return .double(d)
        case let s as String: return .string(s)
        case let a as [Any]: return .array(a.map(wrap))
        case let o as [String: Any]: return .from(o)
        default: return .string(String(describing: v))
        }
    }
}

public struct User: Codable, Sendable {
    public let id: Int
    public let username: String
    public let fullName: String
    /// "" on servers that predate them.
    public let firstName: String
    public let lastName: String
    public let email: String
    /// Gates staff-only UI (dashboard editing); false for service tokens and on older servers.
    public let isStaff: Bool

    enum CodingKeys: String, CodingKey {
        case id, username, email
        case fullName = "full_name", firstName = "first_name", lastName = "last_name"
        case isStaff = "is_staff"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.id = try c.decode(Int.self, forKey: .id)
        self.username = try c.decode(String.self, forKey: .username)
        self.fullName = try c.decode(String.self, forKey: .fullName)
        self.firstName = (try? c.decode(String.self, forKey: .firstName)) ?? ""
        self.lastName = (try? c.decode(String.self, forKey: .lastName)) ?? ""
        self.email = (try? c.decode(String.self, forKey: .email)) ?? ""
        self.isStaff = (try? c.decode(Bool.self, forKey: .isStaff)) ?? false
    }
}

/// Lightweight installation DTO returned by `/me`. Distinct from the
/// `Installation` handle class which exposes resources.
public struct InstallationDTO: Codable, Sendable {
    public let installationId: Int
    public let name: String

    enum CodingKeys: String, CodingKey {
        case installationId = "installation_id"
        case name
    }
}

public struct Me: Codable, Sendable {
    public let user: User
    public let installations: [InstallationDTO]
    /// `nil` for a user with no installations (the server sends `null`).
    public let currentInstallationId: Int?
    /// The user's display-unit choices; `nil` on servers that predate them.
    public let unitPrefs: UnitPrefs?
    /// What each unit may be set to (`updateMe`); `nil` on servers that predate them.
    public let unitChoices: UnitChoices?

    enum CodingKeys: String, CodingKey {
        case user, installations
        case currentInstallationId = "current_installation_id"
        case unitPrefs = "unit_prefs", unitChoices = "unit_choices"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.user = try c.decode(User.self, forKey: .user)
        self.installations = try c.decode([InstallationDTO].self, forKey: .installations)
        self.currentInstallationId = try c.decodeIfPresent(Int.self, forKey: .currentInstallationId)
        // A malformed block must not break sign-in: treat it as absent.
        self.unitPrefs = (try? c.decodeIfPresent(UnitPrefs.self, forKey: .unitPrefs)) ?? nil
        self.unitChoices = (try? c.decodeIfPresent(UnitChoices.self, forKey: .unitChoices)) ?? nil
    }
}

/// The values each display unit accepts, as the web profile offers them.
public struct UnitChoices: Codable, Sendable {
    public let acceleration: [Choice]
    public let velocity: [Choice]
    public let temperature: [Choice]
    public let pressure: [Choice]
    public let frequency: [Choice]
}

/// Per-quantity display units from `/api/me/` (e.g. `velocity: "mm/s"`).
public struct UnitPrefs: Codable, Sendable, Equatable {
    public let acceleration: String
    public let velocity: String
    public let temperature: String
    public let pressure: String
    public let frequency: String
}

/// How to show one data key of a point in the viewer's unit:
/// `display = native * scale + offset`. Storage and entry stay in `native`.
public struct DisplayUnit: Codable, Sendable, Equatable {
    public let native: String
    public let unit: String
    public let scale: Double
    public let offset: Double

    public init(native: String, unit: String, scale: Double, offset: Double) {
        self.native = native
        self.unit = unit
        self.scale = scale
        self.offset = offset
    }

    public func convert(_ value: Double) -> Double { value * scale + offset }
}

/// A gallery photo: the server `File` uuid (what ``Assets/deletePhoto(assetId:uuid:)`` takes) and its absolute URL.
public struct Photo: Codable, Sendable, Equatable {
    public let uuid: String
    public let url: String

    public init(uuid: String, url: String) {
        self.uuid = uuid
        self.url = url
    }
}

public struct Asset: Codable, Sendable {
    public let uuid: String
    public let assetId: Int?
    public let name: String
    public let sectionId: Int?
    public let zoneId: Int?
    public let machineClass: String
    public let equipmentType: String
    public let status: Int
    public let externalId: String?
    // Absolute URLs of the asset's photo gallery, oldest first; `[]` on older servers.
    public let imageUrls: [String]
    /// Same photos as `imageUrls`, with their uuids; `[]` on older servers.
    public let photos: [Photo]
    /// Asset type code, if the asset has one.
    public let assetType: String?

    enum CodingKeys: String, CodingKey {
        case uuid, name, status, photos
        case assetType = "asset_type"
        case imageUrls = "image_urls"
        case assetId = "asset_id"
        case sectionId = "section_id"
        case zoneId = "zone_id"
        case machineClass = "machine_class"
        case equipmentType = "equipment_type"
        case externalId = "external_id"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.assetId = try c.decodeIfPresent(Int.self, forKey: .assetId)
        self.name = try c.decode(String.self, forKey: .name)
        self.sectionId = try c.decodeIfPresent(Int.self, forKey: .sectionId)
        self.zoneId = try c.decodeIfPresent(Int.self, forKey: .zoneId)
        self.machineClass = (try? c.decode(String.self, forKey: .machineClass)) ?? ""
        self.equipmentType = (try? c.decode(String.self, forKey: .equipmentType)) ?? ""
        self.status = try c.decode(Int.self, forKey: .status)
        self.externalId = try c.decodeIfPresent(String.self, forKey: .externalId)
        self.imageUrls = (try? c.decode([String].self, forKey: .imageUrls)) ?? []
        self.photos = (try? c.decode([Photo].self, forKey: .photos)) ?? []
        self.assetType = try c.decodeIfPresent(String.self, forKey: .assetType)
    }
}

public struct MeasurementPoint: Codable, Sendable {
    public let uuid: String
    public let pointId: Int?
    public let name: String
    public let assetId: Int?
    // Optional metadata, drift-plausible from a legacy import. The server
    // columns are `blank=True, default=""` NOT NULL by intent, but if a
    // future server regression or import drift ever sends `null` (or omits
    // the key), the per-field `(try? decode(...)) ?? ""` pattern used
    // everywhere else in this file keeps decode resilient instead of
    // throwing. See issue #2.
    public let transducerType: String
    public let measurementUnitCode: String
    public let location: String
    public let status: Int
    public let externalId: String?
    // Effective working instruction (the point's override, else the
    // transducer-type default) as sanitized HTML; embedded image URLs are
    // absolute. Server always populates it; the resilient `?? ""` decode keeps
    // it safe against drift.
    public let instructions: String
    // `[reference photo URL]`, or `[]` when the point has no photos; the full gallery is `photos`.
    // Absent on older servers, so it decodes to `[]`.
    public let imageUrls: [String]
    /// Data keys whose display unit differs from native for this viewer;
    /// `[:]` when none do, and on servers that predate it.
    public let displayUnits: [String: DisplayUnit]
    /// All of the point's gallery photos with their uuids (`imageUrls` is the reference photo only); `[]` on older servers.
    public let photos: [Photo]
    /// Uuid of the point's reference photo (one of `photos`); `nil` when unset, and on older servers.
    public let referencePhotoUuid: String?
    /// Nameplate shaft speed, rpm.
    public let nominalRpm: Int?
    /// The fitted bearing's uuid (``Bearings/get(uuid:)``).
    public let bearing: String?
    /// Bearing shaft ÷ measured shaft; 1 when unset and on older servers.
    public let speedRatio: Double
    /// Envelope band edges, Hz; nil = default.
    public let envelopeBandLow: Int?
    public let envelopeBandHigh: Int?
    /// False: `instructions` is the transducer type's default.
    public let hasOwnInstructions: Bool

    enum CodingKeys: String, CodingKey {
        case uuid, name, location, status, instructions, photos, bearing
        case nominalRpm = "nominal_rpm", speedRatio = "speed_ratio", envelopeBandLow = "envelope_band_low"
        case envelopeBandHigh = "envelope_band_high", hasOwnInstructions = "has_own_instructions"
        case imageUrls = "image_urls"
        case displayUnits = "display_units"
        case referencePhotoUuid = "reference_photo_uuid"
        case pointId = "point_id"
        case assetId = "asset_id"
        case transducerType = "transducer_type"
        case measurementUnitCode = "measurement_unit_code"
        case externalId = "external_id"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.pointId = try c.decodeIfPresent(Int.self, forKey: .pointId)
        self.name = try c.decode(String.self, forKey: .name)
        self.assetId = try c.decodeIfPresent(Int.self, forKey: .assetId)
        self.transducerType = (try? c.decode(String.self, forKey: .transducerType)) ?? ""
        self.measurementUnitCode = (try? c.decode(String.self, forKey: .measurementUnitCode)) ?? ""
        self.location = (try? c.decode(String.self, forKey: .location)) ?? ""
        self.status = try c.decode(Int.self, forKey: .status)
        self.externalId = try c.decodeIfPresent(String.self, forKey: .externalId)
        self.instructions = (try? c.decode(String.self, forKey: .instructions)) ?? ""
        self.imageUrls = (try? c.decode([String].self, forKey: .imageUrls)) ?? []
        self.displayUnits = (try? c.decode([String: DisplayUnit].self, forKey: .displayUnits)) ?? [:]
        self.photos = (try? c.decode([Photo].self, forKey: .photos)) ?? []
        self.referencePhotoUuid = try c.decodeIfPresent(String.self, forKey: .referencePhotoUuid)
        self.nominalRpm = try c.decodeIfPresent(Int.self, forKey: .nominalRpm)
        self.bearing = try c.decodeIfPresent(String.self, forKey: .bearing)
        self.speedRatio = (try? c.decode(Double.self, forKey: .speedRatio)) ?? 1
        self.envelopeBandLow = try c.decodeIfPresent(Int.self, forKey: .envelopeBandLow)
        self.envelopeBandHigh = try c.decodeIfPresent(Int.self, forKey: .envelopeBandHigh)
        self.hasOwnInstructions = (try? c.decode(Bool.self, forKey: .hasOwnInstructions)) ?? false
    }
}

/// A point's run state, staleness, limits and last 7 days, all in native units
/// (convert with ``MeasurementPoint/displayUnits``).
public struct PointContext: Codable, Sendable, Equatable {
    public let dataKey: String
    public let unit: String
    /// `nil` when the point has no run-state reading (most non-vibration points).
    public let running: Bool?
    public let runningAt: String?
    public let staleSince: String?
    public let limits: PointLimits?
    /// 6 h bin means, chronological; empty bins are omitted.
    public let week: [TrendBin]

    enum CodingKeys: String, CodingKey {
        case unit, running, limits, week
        case dataKey = "data_key"
        case runningAt = "running_at"
        case staleSince = "stale_since"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.dataKey = (try? c.decode(String.self, forKey: .dataKey)) ?? ""
        self.unit = (try? c.decode(String.self, forKey: .unit)) ?? ""
        self.running = try c.decodeIfPresent(Bool.self, forKey: .running)
        self.runningAt = try c.decodeIfPresent(String.self, forKey: .runningAt)
        self.staleSince = try c.decodeIfPresent(String.self, forKey: .staleSince)
        self.limits = try c.decodeIfPresent(PointLimits.self, forKey: .limits)
        self.week = (try? c.decode([TrendBin].self, forKey: .week)) ?? []
    }
}

public struct PointLimits: Codable, Sendable, Equatable {
    public let minor: Double?
    public let major: Double?
}

/// One trend bin: `t` is the bin start (ISO 8601, like every other SDK datetime), `v` the mean.
public struct TrendBin: Codable, Sendable, Equatable {
    public let t: String
    public let v: Double
}

public struct Measurement: Codable, Sendable {
    public let uuid: String
    public let measurementPointId: Int
    // `point_sequence` is genuinely DB-nullable on the server
    // (`Measurement.point_sequence: null=True`); new rows always get a
    // value via `MeasurementService.create`, but legacy/imported rows can
    // be null. `decode(Int.self)` throws on null; switch to
    // `decodeIfPresent` to mirror the Kotlin `Int? = null` widening from
    // the SDK#2 fix. See issue #2.
    public let pointSequence: Int?
    public let data: JSONValue
    public let status: String
    public let notes: String
    public let createdAt: String
    public let fileUrl: String?
    public let externalId: String?

    enum CodingKeys: String, CodingKey {
        case uuid, data, status, notes
        case measurementPointId = "measurement_point_id"
        case pointSequence = "point_sequence"
        case createdAt = "created_at"
        case fileUrl = "file_url"
        case externalId = "external_id"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.measurementPointId = try c.decode(Int.self, forKey: .measurementPointId)
        self.pointSequence = try c.decodeIfPresent(Int.self, forKey: .pointSequence)
        self.data = (try? c.decode(JSONValue.self, forKey: .data)) ?? .object([:])
        self.status = try c.decode(String.self, forKey: .status)
        self.notes = (try? c.decode(String.self, forKey: .notes)) ?? ""
        self.createdAt = try c.decode(String.self, forKey: .createdAt)
        self.fileUrl = try c.decodeIfPresent(String.self, forKey: .fileUrl)
        self.externalId = try c.decodeIfPresent(String.self, forKey: .externalId)
    }
}

public struct Route: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let description: String
    /// The route's section; nil when it has none, and where the server leaves it out.
    public let section: SectionRef?

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.name = try c.decode(String.self, forKey: .name)
        self.description = (try? c.decode(String.self, forKey: .description)) ?? ""
        self.section = try? c.decodeIfPresent(SectionRef.self, forKey: .section)
    }

    enum CodingKeys: String, CodingKey { case uuid, name, description, section }
}

public struct SectionRef: Codable, Sendable {
    public let sectionId: Int?
    public let name: String
    enum CodingKeys: String, CodingKey { case sectionId = "section_id"; case name }
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.sectionId = try c.decodeIfPresent(Int.self, forKey: .sectionId)
        self.name = (try? c.decode(String.self, forKey: .name)) ?? ""
    }
}

/// Threshold context for a measurement reading (drives "Limit X" + the
/// OK/Watch/Alarm band on the redesigned Point screen). Resolved server-side
/// from the point's threshold alarm rules. All fields default so an absent or
/// partial `limit` decodes cleanly.
public struct MeasurementLimit: Codable, Sendable {
    public let minor: Double?
    public let major: Double?
    public let direction: String
    public let unit: String

    enum CodingKeys: String, CodingKey { case minor, major, direction, unit }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.minor = try c.decodeIfPresent(Double.self, forKey: .minor)
        self.major = try c.decodeIfPresent(Double.self, forKey: .major)
        self.direction = (try? c.decode(String.self, forKey: .direction)) ?? "high"
        self.unit = (try? c.decode(String.self, forKey: .unit)) ?? ""
    }
}

public struct RouteItem: Codable, Sendable {
    public let uuid: String
    public let checkId: Int?
    public let label: String
    public let itemType: String
    public let assetId: Int?
    public let zoneId: Int?
    public let zoneName: String?
    public let measurementPointId: Int?
    public let config: JSONValue
    // First-class, server-resolved fields for the redesigned Point screen.
    // Additive with defaults so legacy payloads decode unchanged.
    public let instructions: [String]
    public let referenceImageUrl: String?
    public let limit: MeasurementLimit?
    enum CodingKeys: String, CodingKey {
        case uuid, label, config, instructions, limit
        case checkId = "check_id"; case itemType = "item_type"
        case assetId = "asset_id"; case zoneId = "zone_id"; case zoneName = "zone_name"
        case measurementPointId = "measurement_point_id"
        case referenceImageUrl = "reference_image_url"
    }
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.checkId = try c.decodeIfPresent(Int.self, forKey: .checkId)
        self.label = (try? c.decode(String.self, forKey: .label)) ?? ""
        self.itemType = (try? c.decode(String.self, forKey: .itemType)) ?? ""
        self.assetId = try c.decodeIfPresent(Int.self, forKey: .assetId)
        self.zoneId = try c.decodeIfPresent(Int.self, forKey: .zoneId)
        self.zoneName = try c.decodeIfPresent(String.self, forKey: .zoneName)
        self.measurementPointId = try c.decodeIfPresent(Int.self, forKey: .measurementPointId)
        self.config = (try? c.decode(JSONValue.self, forKey: .config)) ?? .object([:])
        self.instructions = (try? c.decode([String].self, forKey: .instructions)) ?? []
        self.referenceImageUrl = try c.decodeIfPresent(String.self, forKey: .referenceImageUrl)
        self.limit = try c.decodeIfPresent(MeasurementLimit.self, forKey: .limit)
    }
}

public struct RouteDetail: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let description: String
    public let section: SectionRef?
    public let items: [RouteItem]
    enum CodingKeys: String, CodingKey { case uuid, name, description, section, items }
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.name = (try? c.decode(String.self, forKey: .name)) ?? ""
        self.description = (try? c.decode(String.self, forKey: .description)) ?? ""
        self.section = try c.decodeIfPresent(SectionRef.self, forKey: .section)
        self.items = (try? c.decode([RouteItem].self, forKey: .items)) ?? []
    }
}

public struct RouteExecution: Codable, Sendable {
    public let uuid: String
    public let routeUuid: String
    public let status: String
    public let startedAt: String?
    public let completedAt: String?
    public let sessionId: String

    enum CodingKeys: String, CodingKey {
        case uuid, status
        case routeUuid = "route_uuid"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case sessionId = "session_id"
    }
}

public struct ItemResponse: Codable, Sendable {
    public let uuid: String
    public let routeItemUuid: String
    public let data: JSONValue
    public let notes: String
    public let status: Int
    public let createdAt: String

    enum CodingKeys: String, CodingKey {
        case uuid, data, notes, status
        case routeItemUuid = "route_item_uuid"
        case createdAt = "created_at"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.routeItemUuid = try c.decode(String.self, forKey: .routeItemUuid)
        self.data = (try? c.decode(JSONValue.self, forKey: .data)) ?? .object([:])
        self.notes = (try? c.decode(String.self, forKey: .notes)) ?? ""
        self.status = try c.decode(Int.self, forKey: .status)
        self.createdAt = try c.decode(String.self, forKey: .createdAt)
    }
}

/// Generic paginated wrapper used by list endpoints.
struct Page<T: Decodable & Sendable>: Decodable, Sendable {
    let items: [T]
    let total: Int?
    let limit: Int?
    let offset: Int?
}

public struct Section: Codable, Sendable {
    public let uuid: String
    public let sectionId: Int?
    public let name: String
    public let externalId: String?
    enum CodingKeys: String, CodingKey {
        case uuid, name
        case sectionId = "section_id"
        case externalId = "external_id"
    }
}

public struct Zone: Codable, Sendable {
    public let uuid: String
    public let zoneId: Int?
    public let name: String
    public let sectionId: Int?
    public let externalId: String?
    /// Public guest page enabled; `false` on older servers.
    public let guestView: Bool
    enum CodingKeys: String, CodingKey {
        case uuid, name
        case zoneId = "zone_id"
        case sectionId = "section_id"
        case externalId = "external_id"
        case guestView = "guest_view"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.zoneId = try c.decodeIfPresent(Int.self, forKey: .zoneId)
        self.name = try c.decode(String.self, forKey: .name)
        self.sectionId = try c.decodeIfPresent(Int.self, forKey: .sectionId)
        self.externalId = try c.decodeIfPresent(String.self, forKey: .externalId)
        self.guestView = try c.decodeIfPresent(Bool.self, forKey: .guestView) ?? false
    }
}

/// Asset type (template), addressed by `code`.
public struct AssetType: Codable, Sendable {
    public let uuid: String
    public let code: String
    public let name: String
    public let manufacturer: String
    public let checklist: [JSONValue]
    public let externalId: String?
    public let assetCount: Int
    public let documentCount: Int

    enum CodingKeys: String, CodingKey {
        case uuid, code, name, manufacturer, checklist
        case externalId = "external_id"
        case assetCount = "asset_count"
        case documentCount = "document_count"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.code = try c.decode(String.self, forKey: .code)
        self.name = try c.decode(String.self, forKey: .name)
        self.manufacturer = (try? c.decode(String.self, forKey: .manufacturer)) ?? ""
        self.checklist = (try? c.decode([JSONValue].self, forKey: .checklist)) ?? []
        self.externalId = try c.decodeIfPresent(String.self, forKey: .externalId)
        self.assetCount = (try? c.decode(Int.self, forKey: .assetCount)) ?? 0
        self.documentCount = (try? c.decode(Int.self, forKey: .documentCount)) ?? 0
    }
}

/// Result of ``Assets/ensureChecklist(assetId:)``.
public struct ChecklistResult: Codable, Sendable {
    public let routeUuid: String
    public let created: Bool
    enum CodingKeys: String, CodingKey { case routeUuid = "route_uuid", created }
}

public struct DeleteResult: Codable, Sendable {
    public let deleted: Bool
    public let uuid: String
}

public struct BatchItemResult: Codable, Sendable {
    public let index: Int
    public let status: String
    public let measurementPointId: Int?
    public let pointSequence: Int?
    public let uuid: String?
    public let externalId: String?
    public let detail: String?
    enum CodingKeys: String, CodingKey {
        case index, status, uuid, detail
        case measurementPointId = "measurement_point_id"
        case pointSequence = "point_sequence"
        case externalId = "external_id"
    }
}

public struct BatchResult: Codable, Sendable {
    public let created: Int
    public let duplicates: Int
    public let errors: Int
    public let results: [BatchItemResult]
}

public struct FileAttachment: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let kind: String
    public let fileUrl: String
    public let createdAt: String
    enum CodingKeys: String, CodingKey {
        case uuid, name, kind
        case fileUrl = "file_url"
        case createdAt = "created_at"
    }
}

/// Cursor-paginated wrapper for history iteration.
struct CursorPage<T: Decodable & Sendable>: Decodable, Sendable {
    let items: [T]
    let nextCursor: String?
    enum CodingKeys: String, CodingKey {
        case items
        case nextCursor = "next_cursor"
    }
}

/// A photo to upload via multipart.
public struct PhotoUpload: Sendable {
    public let filename: String
    public let mimeType: String
    public let data: Data

    public init(filename: String, mimeType: String = "image/jpeg", data: Data) {
        self.filename = filename
        self.mimeType = mimeType
        self.data = data
    }

    public init(fileURL: URL, mimeType: String = "image/jpeg") throws {
        self.filename = fileURL.lastPathComponent
        self.mimeType = mimeType
        self.data = try Data(contentsOf: fileURL)
    }
}
