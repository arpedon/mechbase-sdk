import Foundation

// MaintNode on-site commissioning: scan the label (`/provision/<balena_uuid>/`), look it up, claim it,
// then poll ``Devices/get(nodeUuid:)``: `tokenPush.state == "pushed"` → first heartbeat
// (`lastSeenAt` / `isOnline`) → `config.isCurrent == true`. Service tokens get 403 on lookup and claim.

/// A Balena device uuid, dashed or the 32-hex form the labels carry (the server takes both).
private func requireBalenaUUID(_ s: String) throws {
    let hex = s.count == 32 && s.allSatisfy(\.isHexDigit)
    guard hex || UUID(uuidString: s) != nil else { throw MechbaseError.validation("invalid balena uuid: \(s)") }
}

extension Devices {
    private struct ClaimBody: Encodable { let balena_uuid: String; let name: String? }

    /// What the provision page shows for a device label: `state` is claim | member (already in this
    /// installation) | taken | not_found | unreachable (Balena did not answer; try again).
    public func lookup(balenaUuid: String) async throws -> DeviceLookup {
        try requireBalenaUUID(balenaUuid)
        return try await scope.http.get(scope.path("/devices/lookup/\(balenaUuid)"), as: DeviceLookup.self)
    }

    /// Claim the device into this installation and queue its credentials. Already ours: credentials are
    /// sent again and the name is kept. Another installation's: 409.
    public func claim(balenaUuid: String, name: String? = nil) async throws -> Device {
        try requireBalenaUUID(balenaUuid)
        return try await scope.http.postJSON(scope.path("/devices"), body: ClaimBody(balena_uuid: balenaUuid, name: name),
                                             as: Device.self)
    }

    /// Queue the push of the device's current token again; follow `tokenPush` on the result.
    public func resendCredentials(nodeUuid: String) async throws -> Device {
        try requireUUID(nodeUuid)
        return try await scope.http.post(scope.path("/devices/\(nodeUuid)/credentials"), as: Device.self)
    }

    /// Every channel slot per group, free or with the point it feeds (Modbus: used registers only).
    public func channels(nodeUuid: String) async throws -> [GroupChannels] {
        try requireUUID(nodeUuid)
        return try await scope.http.get(scope.path("/devices/\(nodeUuid)/channels"), as: [GroupChannels].self)
    }

    /// The add-source page's new group: `group_name`, `hardware_type` (hat|ul|modbus), `hardware_address` /
    /// `hardware_id` (USB DAQ), `interval`, `sample_rate`, `samples`, and the Modbus connection fields.
    /// Returns the device; the new group is the one named `group_name`.
    public func createGroup(nodeUuid: String, fields: [String: JSONValue]) async throws -> Device {
        try requireUUID(nodeUuid)
        return try await scope.http.postJSON(scope.path("/devices/\(nodeUuid)/groups"), body: fields, as: Device.self)
    }
}

public struct TokenPush: Codable, Sendable {
    public let state: String
    public let queuedAt: String?
    public let pushedAt: String?
    public let failedAt: String?
    enum CodingKeys: String, CodingKey {
        case state
        case queuedAt = "queued_at", pushedAt = "pushed_at", failedAt = "failed_at"
    }
}

public struct DeviceConfig: Codable, Sendable {
    public let appliedVersion: String?
    public let currentVersion: String
    public let isCurrent: Bool?
    enum CodingKeys: String, CodingKey {
        case appliedVersion = "applied_version", currentVersion = "current_version", isCurrent = "is_current"
    }
}

public struct DeviceLookup: Codable, Sendable {
    public let state: String
    public let nodeUuid: String
    public let name: String?
    public let installationId: Int?
    public let installationName: String?
    public let isOnline: Bool?
    enum CodingKeys: String, CodingKey {
        case state, name
        case nodeUuid = "node_uuid", installationId = "installation_id", installationName = "installation_name"
        case isOnline = "is_online"
    }
}

public struct GroupChannels: Codable, Sendable {
    public let uuid: String
    public let name: String
    public let hardwareType: String
    public let slots: Int?
    public let channels: [ChannelSlot]
    enum CodingKeys: String, CodingKey {
        case uuid, name, slots, channels
        case hardwareType = "hardware_type"
    }
}

public struct ChannelSlot: Codable, Sendable {
    public let channel: Int
    public let used: Bool
    public let mappingUuid: String?
    public let isActive: Bool?
    public let pointId: Int?
    public let pointName: String?
    public let assetId: Int?
    public let assetName: String?
    public let sensor: String?
    public let state: String?
    enum CodingKeys: String, CodingKey {
        case channel, used, sensor, state
        case mappingUuid = "mapping_uuid", isActive = "is_active", pointId = "point_id", pointName = "point_name"
        case assetId = "asset_id", assetName = "asset_name"
    }
}
