import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Internal HTTP transport. Actor-isolated so it is safe to share across tasks.
actor HTTPClient {
    let baseURL: URL
    let token: String
    let session: URLSession
    let decoder: JSONDecoder
    let encoder: JSONEncoder

    init(baseURL: URL, token: String, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.token = token
        self.session = session
        let dec = JSONDecoder()
        // The API returns ISO8601 strings; we keep `created_at` etc. as strings to
        // mirror the Python SDK 1:1, but the decoder is configured for any future
        // `Date` properties.
        dec.dateDecodingStrategy = .iso8601
        self.decoder = dec
        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        self.encoder = enc
    }

    // MARK: - URL building

    private func url(path: String, query: [URLQueryItem] = []) -> URL {
        // Preserve trailing slashes by hand-building the string — URLComponents
        // will silently strip them when round-tripping `path`.
        var base = baseURL.absoluteString
        if base.hasSuffix("/") { base.removeLast() }
        var combined = base + path
        let filtered = query.filter { $0.value != nil && $0.value != "" }
        if !filtered.isEmpty {
            var qs: [String] = []
            for item in filtered {
                let k = item.name.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? item.name
                let v = (item.value ?? "").addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
                qs.append("\(k)=\(v)")
            }
            combined += "?" + qs.joined(separator: "&")
        }
        return URL(string: combined) ?? baseURL
    }

    private func makeRequest(_ method: String, _ url: URL) -> URLRequest {
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.setValue("mechbase-swift/0.1", forHTTPHeaderField: "User-Agent")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        return req
    }

    // MARK: - Verbs

    func get<T: Decodable>(_ path: String, query: [URLQueryItem] = [], as: T.Type) async throws -> T {
        let req = makeRequest("GET", url(path: path, query: query))
        return try await send(req)
    }

    func post<T: Decodable>(_ path: String, as: T.Type) async throws -> T {
        let req = makeRequest("POST", url(path: path))
        return try await send(req)
    }

    func postJSON<T: Decodable, B: Encodable>(_ path: String, body: B, as: T.Type) async throws -> T {
        var req = makeRequest("POST", url(path: path))
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(body)
        return try await send(req)
    }

    func postMultipart<T: Decodable>(
        _ path: String,
        fields: [String: String],
        files: [(name: String, filename: String, mimeType: String, data: Data)],
        as: T.Type
    ) async throws -> T {
        let boundary = "----MechbaseSwiftBoundary\(UUID().uuidString)"
        var req = makeRequest("POST", url(path: path))
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.httpBody = Self.buildMultipart(boundary: boundary, fields: fields, files: files)
        return try await send(req)
    }

    static func buildMultipart(
        boundary: String,
        fields: [String: String],
        files: [(name: String, filename: String, mimeType: String, data: Data)]
    ) -> Data {
        var body = Data()
        let crlf = "\r\n"
        for (k, v) in fields {
            body.append("--\(boundary)\(crlf)".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(k)\"\(crlf)\(crlf)".data(using: .utf8)!)
            body.append(v.data(using: .utf8)!)
            body.append(crlf.data(using: .utf8)!)
        }
        for f in files {
            body.append("--\(boundary)\(crlf)".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(f.name)\"; filename=\"\(f.filename)\"\(crlf)".data(using: .utf8)!)
            body.append("Content-Type: \(f.mimeType)\(crlf)\(crlf)".data(using: .utf8)!)
            body.append(f.data)
            body.append(crlf.data(using: .utf8)!)
        }
        body.append("--\(boundary)--\(crlf)".data(using: .utf8)!)
        return body
    }

    // MARK: - Send + decode

    private func send<T: Decodable>(_ req: URLRequest) async throws -> T {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw MechbaseError.transport(error)
        }
        guard let http = response as? HTTPURLResponse else {
            throw MechbaseError.server(0, "no http response")
        }
        let status = http.statusCode
        if (200..<300).contains(status) {
            if T.self == EmptyResponse.self {
                // swiftlint:disable:next force_cast
                return EmptyResponse() as! T
            }
            do {
                return try decoder.decode(T.self, from: data)
            } catch {
                throw MechbaseError.transport(error)
            }
        }
        let detail = Self.extractDetail(data) ?? ""
        let message = "\(status) \(detail)"
        switch status {
        case 401, 403: throw MechbaseError.auth(message)
        case 404: throw MechbaseError.notFound(message)
        case 422: throw MechbaseError.validation(message)
        default: throw MechbaseError.server(status, message)
        }
    }

    private static func extractDetail(_ data: Data) -> String? {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return String(data: data, encoding: .utf8)
        }
        return obj["detail"] as? String
    }
}

/// Sentinel for endpoints that return 204 / nothing useful.
struct EmptyResponse: Decodable { init() {} }
