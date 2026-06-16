import Foundation

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
    public let email: String

    enum CodingKeys: String, CodingKey {
        case id, username, email
        case fullName = "full_name"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.id = try c.decode(Int.self, forKey: .id)
        self.username = try c.decode(String.self, forKey: .username)
        self.fullName = try c.decode(String.self, forKey: .fullName)
        self.email = (try? c.decode(String.self, forKey: .email)) ?? ""
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
    public let currentInstallationId: Int

    enum CodingKeys: String, CodingKey {
        case user, installations
        case currentInstallationId = "current_installation_id"
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

    enum CodingKeys: String, CodingKey {
        case uuid, name, status
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
    }
}

public struct MeasurementPoint: Codable, Sendable {
    public let uuid: String
    public let pointId: Int?
    public let name: String
    public let assetId: Int?
    public let transducerType: String
    public let measurementUnitCode: String
    public let location: String
    public let status: Int
    public let externalId: String?

    enum CodingKeys: String, CodingKey {
        case uuid, name, location, status
        case pointId = "point_id"
        case assetId = "asset_id"
        case transducerType = "transducer_type"
        case measurementUnitCode = "measurement_unit_code"
        case externalId = "external_id"
    }
}

public struct Measurement: Codable, Sendable {
    public let uuid: String
    public let measurementPointId: Int
    public let pointSequence: Int
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
        self.pointSequence = try c.decode(Int.self, forKey: .pointSequence)
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

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.name = try c.decode(String.self, forKey: .name)
        self.description = (try? c.decode(String.self, forKey: .description)) ?? ""
    }

    enum CodingKeys: String, CodingKey { case uuid, name, description }
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
struct Page<T: Decodable>: Decodable {
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
    enum CodingKeys: String, CodingKey {
        case uuid, name
        case zoneId = "zone_id"
        case sectionId = "section_id"
        case externalId = "external_id"
    }
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
struct CursorPage<T: Decodable>: Decodable {
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
