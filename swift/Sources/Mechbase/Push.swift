import Foundation

public enum PushPlatform: String, Codable, Sendable {
    case apns, fcm
}

extension MechbaseClient {
    private struct PushDeviceBody: Encodable { let platform: PushPlatform; let token: String; let app_version: String }

    /// Register this device for push, after sign-in and whenever the platform token changes. Upserts by
    /// `token` and is tied to the calling API token: revoking it removes the registration.
    /// An APNs token is hex (64–200 characters).
    @discardableResult
    public func registerPushDevice(platform: PushPlatform, token: String, appVersion: String = "") async throws -> PushDevice {
        try await http.postJSON("/api/push/devices",
                                body: PushDeviceBody(platform: platform, token: token, app_version: appVersion),
                                as: PushDevice.self)
    }

    /// Drop the registration on sign-out (best effort). 404 (``MechbaseError/notFound(_:)``) when already gone.
    public func deletePushDevice(token: String) async throws {
        // An FCM token carries `:`; anything that could leave the path segment is escaped.
        let segment = token.addingPercentEncoding(withAllowedCharacters: .alphanumerics.union(CharacterSet(charactersIn: "-._~"))) ?? token
        _ = try await http.delete("/api/push/devices/\(segment)", as: EmptyResponse.self)
    }
}

public struct PushDevice: Codable, Sendable {
    public let platform: String
    public let token: String
    public let appVersion: String
    public let createdAt: String
    public let lastSeenAt: String
    enum CodingKeys: String, CodingKey {
        case platform, token
        case appVersion = "app_version", createdAt = "created_at", lastSeenAt = "last_seen_at"
    }
}
