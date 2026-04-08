import Foundation
#if canImport(Security)
import Security

/// Keychain-backed token storage for client apps (iOS Hotwire Native, macOS tools).
/// Stores a single bearer token per `(service, account)` pair.
///
/// ```swift
/// let store = TokenStore(service: "io.mechbase.ios")
/// try store.save("abc123", account: "default")
/// if let token = try store.load(account: "default") {
///     let client = MechbaseClient(token: token)
/// }
/// ```
public struct TokenStore: Sendable {
    public let service: String

    public init(service: String) {
        self.service = service
    }

    public func save(_ token: String, account: String = "default") throws {
        let data = Data(token.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let attrs: [String: Any] = [kSecValueData as String: data]

        let status = SecItemUpdate(query as CFDictionary, attrs as CFDictionary)
        if status == errSecItemNotFound {
            var insert = query
            insert[kSecValueData as String] = data
            insert[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
            let addStatus = SecItemAdd(insert as CFDictionary, nil)
            guard addStatus == errSecSuccess else { throw KeychainError(status: addStatus) }
            return
        }
        guard status == errSecSuccess else { throw KeychainError(status: status) }
    }

    public func load(account: String = "default") throws -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess else { throw KeychainError(status: status) }
        guard let data = result as? Data, let token = String(data: data, encoding: .utf8) else {
            return nil
        }
        return token
    }

    public func delete(account: String = "default") throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError(status: status)
        }
    }
}

public struct KeychainError: Error, CustomStringConvertible {
    public let status: OSStatus
    public var description: String { "KeychainError(\(status))" }
}

public extension MechbaseClient {
    /// Convenience initializer that loads the bearer token from the Keychain.
    /// Returns `nil` if no token is stored.
    static func fromKeychain(service: String, account: String = "default",
                             baseURL: URL = MechbaseClient.defaultBaseURL) throws -> MechbaseClient? {
        let store = TokenStore(service: service)
        guard let token = try store.load(account: account) else { return nil }
        return MechbaseClient(token: token, baseURL: baseURL)
    }
}
#endif
