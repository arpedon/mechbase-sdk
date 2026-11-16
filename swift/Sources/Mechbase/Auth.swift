import Foundation
import CryptoKit
import Security

/// Unauthenticated sign-in calls, made before there is a bearer token.
///
/// Microsoft sign-in from an app:
/// ```swift
/// let auth = MechbaseAuth()                       // or MechbaseAuth(baseURL: selfHosted)
/// guard await auth.ssoCheck(email: email) else { return }  // show "Sign in with Microsoft"?
/// let pkce = PKCE.generate()
/// let url = auth.ssoStartURL(codeChallenge: pkce.challenge, loginHint: email)
/// // open `url` in ASWebAuthenticationSession (callback scheme "mechbase"),
/// // read `code` from the mechbase://sso?code=… callback, then:
/// let token = try await auth.exchangeSSOCode(code: code, codeVerifier: pkce.verifier, deviceId: deviceId)
/// let client = MechbaseClient(token: token)
/// ```
public struct MechbaseAuth: Sendable {
    let http: HTTPClient

    public init(baseURL: URL = MechbaseClient.defaultBaseURL, session: URLSession = .shared) {
        self.http = HTTPClient(baseURL: baseURL, token: "", session: session)
    }

    private struct SSOCheck: Decodable { let sso: Bool }
    private struct TokenOut: Decodable { let token: String }
    private struct ExchangeIn: Encodable {
        let code: String
        let codeVerifier: String
        let deviceId: String?
        enum CodingKeys: String, CodingKey {
            case code
            case codeVerifier = "code_verifier"
            case deviceId = "device_id"
        }
    }

    /// Whether `email` signs in with Microsoft. Any error (network, 4xx/5xx, bad body) is `false`.
    public func ssoCheck(email: String) async -> Bool {
        (try? await http.get("/sso/check/", query: [URLQueryItem(name: "email", value: email)],
                             as: SSOCheck.self).sso) ?? false
    }

    /// The page that starts Microsoft sign-in; it ends on `mechbase://sso?code=…` (or `?error=…`).
    public func ssoStartURL(codeChallenge: String, loginHint: String? = nil) -> URL {
        http.url(path: "/sso/native/start/", query: [
            URLQueryItem(name: "code_challenge", value: codeChallenge),
            URLQueryItem(name: "code_challenge_method", value: "S256"),
            URLQueryItem(name: "login_hint", value: loginHint),
        ])
    }

    /// Trade the one-time `code` from the callback for a bearer token (single use).
    /// Throws ``MechbaseError/auth(_:)`` with the server's message on a rejected code
    /// (400: expired, used, or a verifier that doesn't match).
    public func exchangeSSOCode(code: String, codeVerifier: String, deviceId: String? = nil) async throws -> String {
        do {
            return try await http.postJSON(
                "/api/auth/sso/exchange",
                body: ExchangeIn(code: code, codeVerifier: codeVerifier, deviceId: deviceId),
                as: TokenOut.self
            ).token
        } catch MechbaseError.server(400, let message) {
            throw MechbaseError.auth(message)
        }
    }
}

/// RFC 7636 PKCE (S256).
public enum PKCE {
    /// A fresh verifier (32 random bytes, base64url, 43 chars) and its S256 challenge.
    public static func generate() -> (verifier: String, challenge: String) {
        var bytes = [UInt8](repeating: 0, count: 32)
        let status = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        precondition(status == errSecSuccess, "SecRandomCopyBytes failed: \(status)")
        let verifier = base64url(Data(bytes))
        return (verifier, challenge(for: verifier))
    }

    /// base64url(SHA-256(ASCII(verifier))), no padding.
    public static func challenge(for verifier: String) -> String {
        base64url(Data(SHA256.hash(data: Data(verifier.utf8))))
    }

    static func base64url(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
