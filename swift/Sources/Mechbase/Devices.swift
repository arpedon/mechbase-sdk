import Foundation

/// One mapped channel of a MaintNode group. `state` is ok | stale | waiting.
public struct DeviceChannel: Codable, Sendable {
    public let uuid: String
    public let channel: Int?
    public let pointId: Int
    public let pointName: String
    public let assetId: Int
    public let assetName: String
    public let sensor: String
    public let lastSeenAt: String?
    public let staleSince: String?
    public let state: String
    enum CodingKeys: String, CodingKey {
        case uuid, channel, sensor, state
        case pointId = "point_id", pointName = "point_name", assetId = "asset_id", assetName = "asset_name"
        case lastSeenAt = "last_seen_at", staleSince = "stale_since"
    }
}

public struct DeviceGroup: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let hardwareType: String
    public let hardwareConfig: JSONValue
    public let interval: Int
    public let sampleRate: Int?
    public let samples: Int?
    public let channels: [DeviceChannel]
    enum CodingKeys: String, CodingKey {
        case uuid, name, interval, samples, channels
        case hardwareType = "hardware_type", hardwareConfig = "hardware_config", sampleRate = "sample_rate"
    }
}

/// Remote access to a service on a device's site: http opens in a browser at `webUrl`;
/// stcp needs frpc and the visitor file (staff). The installation and device fields are
/// set only in the staff list across installations (`MechbaseClient.tunnels()`).
public struct Tunnel: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let label: String
    public let kind: String
    public let staffOnly: Bool
    public let webUrl: String?
    public let localPort: Int?
    public let visitorUrl: String?
    public let installationId: Int?
    public let installationName: String?
    public let nodeUuid: String?
    public let deviceName: String?
    enum CodingKeys: String, CodingKey {
        case uuid, name, label, kind
        case staffOnly = "staff_only", webUrl = "web_url", localPort = "local_port", visitorUrl = "visitor_url"
        case installationId = "installation_id", installationName = "installation_name"
        case nodeUuid = "node_uuid", deviceName = "device_name"
    }
}

/// A MaintNode with its groups, channels and the tunnels you may open. `healthUrl` is set for staff only.
public struct Device: Codable, Sendable {
    public let nodeUuid: String
    public let name: String
    public let isOnline: Bool
    public let lastSeenAt: String?
    public let claimedAt: String?
    public let health: JSONValue
    public let healthWarnings: [String]
    public let healthUrl: String?
    public let groups: [DeviceGroup]
    public let tunnels: [Tunnel]
    enum CodingKeys: String, CodingKey {
        case name, health, groups, tunnels
        case nodeUuid = "node_uuid", isOnline = "is_online", lastSeenAt = "last_seen_at", claimedAt = "claimed_at"
        case healthWarnings = "health_warnings", healthUrl = "health_url"
    }
}

public struct SourceGroup: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let hardwareType: String
    enum CodingKeys: String, CodingKey { case uuid, name, hardwareType = "hardware_type" }
}

/// One data source feeding a point. `sourceType` is mqtt | maintnode.
public struct Source: Codable, Sendable {
    public let uuid: String
    public let sourceType: String
    public let deviceId: String
    public let deviceName: String?
    public let group: SourceGroup?
    public let channel: Int?
    public let sensor: String
    public let sensorConfig: JSONValue?
    public let isActive: Bool
    public let lastSeenAt: String?
    public let staleSince: String?
    enum CodingKeys: String, CodingKey {
        case uuid, group, channel, sensor
        case sourceType = "source_type", deviceId = "device_id", deviceName = "device_name"
        case sensorConfig = "sensor_config", isActive = "is_active", lastSeenAt = "last_seen_at", staleSince = "stale_since"
    }
}

func requireUUID(_ s: String) throws {
    guard UUID(uuidString: s) != nil else { throw MechbaseError.validation("invalid uuid: \(s)") }
}

/// The installation's MaintNode devices.
public final class Devices: Sendable {
    private let scope: InstallationScope
    init(http: HTTPClient, installationId: Int) { scope = InstallationScope(http: http, installationId: installationId) }

    /// Devices needing attention first.
    public func list() async throws -> [Device] {
        try await scope.http.get(scope.path("/devices"), as: [Device].self)
    }

    public func get(nodeUuid: String) async throws -> Device {
        try requireUUID(nodeUuid)
        return try await scope.http.get(scope.path("/devices/\(nodeUuid)"), as: Device.self)
    }

    public func rename(nodeUuid: String, name: String) async throws -> Device {
        try requireUUID(nodeUuid)
        return try await scope.http.patchJSON(scope.path("/devices/\(nodeUuid)"), body: ["name": name], as: Device.self)
    }

    /// The group edit page's fields (name, interval, sample_rate, samples, hardware_id, hardware_address,
    /// Modbus connection fields); fields left out keep their value. Returns the device.
    public func updateGroup(nodeUuid: String, groupUuid: String, fields: [String: JSONValue]) async throws -> Device {
        try requireUUID(nodeUuid); try requireUUID(groupUuid)
        return try await scope.http.patchJSON(scope.path("/devices/\(nodeUuid)/groups/\(groupUuid)"), body: fields, as: Device.self)
    }
}

/// A point's data sources. Fields are the add-source page's (source_type, mqtt_device_id, device, group,
/// group_name, hardware_type, mn_channel, register_address, sensor, sensitivity, …).
public final class Sources: Sendable {
    private let scope: InstallationScope
    init(http: HTTPClient, installationId: Int) { scope = InstallationScope(http: http, installationId: installationId) }

    private func path(_ pointId: Int, _ suffix: String = "") -> String {
        scope.path("/measurement-points/\(pointId)/sources\(suffix)")
    }

    public func list(pointId: Int) async throws -> [Source] {
        try await scope.http.get(path(pointId), as: [Source].self)
    }

    /// Omitted fields take the page's defaults; a MaintNode source with no group creates one.
    public func create(pointId: Int, fields: [String: JSONValue]) async throws -> Source {
        try await scope.http.postJSON(path(pointId), body: fields, as: Source.self)
    }

    /// Fields left out keep their value; a source keeps its type, device and group.
    public func update(pointId: Int, uuid: String, fields: [String: JSONValue]) async throws -> Source {
        try requireUUID(uuid)
        return try await scope.http.patchJSON(path(pointId, "/\(uuid)"), body: fields, as: Source.self)
    }

    public func delete(pointId: Int, uuid: String) async throws {
        try requireUUID(uuid)
        _ = try await scope.http.delete(path(pointId, "/\(uuid)"), as: EmptyResponse.self)
    }
}

extension MechbaseClient {
    /// Every installation's tunnels (staff only).
    public func tunnels() async throws -> [Tunnel] {
        try await http.get("/api/tunnels", as: [Tunnel].self)
    }

    /// An stcp tunnel's frpc config (staff only): `frpc -c <file>`, then 127.0.0.1:<localPort>. It holds secrets.
    public func tunnelVisitorFile(uuid: String) async throws -> Data {
        try requireUUID(uuid)
        return try await http.getData("/api/tunnels/\(uuid)/visitor.toml")
    }
}
