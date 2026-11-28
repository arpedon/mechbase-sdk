import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// The outcome of a conditional GET (`If-None-Match`).
///
/// Keep the `etag` of the last `.modified` and pass it back on the next poll; on
/// `.notModified` the server sent nothing (304) and the copy you hold is current.
public enum Conditional<T: Sendable>: Sendable {
    /// A new body, with the `ETag` to send next time (nil when the server sent none).
    case modified(T, etag: String?)
    /// 304: nothing changed since `etag`.
    case notModified

    /// The body, or nil on `.notModified`.
    public var value: T? {
        if case .modified(let v, _) = self { return v }
        return nil
    }

    /// The ETag of a `.modified` response.
    public var etag: String? {
        if case .modified(_, let e) = self { return e }
        return nil
    }
}

extension HTTPClient {
    /// GET with `If-None-Match: etag` (sent verbatim: a gzip-weakened `W/"…"` must be echoed as is).
    func getConditional<T: Decodable & Sendable>(_ path: String, query: [URLQueryItem] = [], etag: String?,
                                                 as: T.Type) async throws -> Conditional<T> {
        var req = makeRequest("GET", url(path: path, query: query))
        // Our own validator: URLCache must neither answer from cache nor turn the 304 into a 200.
        req.cachePolicy = .reloadIgnoringLocalCacheData
        if let etag { req.setValue(etag, forHTTPHeaderField: "If-None-Match") }
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw MechbaseError.transport(error)
        }
        guard let http = response as? HTTPURLResponse else { throw MechbaseError.server(0, "no http response") }
        if http.statusCode == 304 { return .notModified }
        guard (200..<300).contains(http.statusCode) else { throw Self.mapError(status: http.statusCode, data: data) }
        do {
            return .modified(try decoder.decode(T.self, from: data), etag: http.value(forHTTPHeaderField: "ETag"))
        } catch {
            throw MechbaseError.transport(error)
        }
    }
}
