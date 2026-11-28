import Foundation

/// Errors thrown by the Mechbase SDK.
public enum MechbaseError: Error, CustomStringConvertible {
    /// 401 / 403.
    case auth(String)
    /// 404.
    case notFound(String)
    /// 409. `body` is the raw response body, so callers can read fields beyond
    /// `detail` (e.g. ``runningExecutionUuid``).
    case conflict(String, body: Data = Data())
    /// 413.
    case tooLarge(String)
    /// 422.
    case validation(String)
    /// Any other non-2xx response.
    case server(Int, String)
    /// URLSession or decoding failure.
    case transport(Error)

    public var description: String {
        switch self {
        case .auth(let m): return "auth: \(m)"
        case .notFound(let m): return "notFound: \(m)"
        case .conflict(let m, _): return "conflict: \(m)"
        case .tooLarge(let m): return "tooLarge: \(m)"
        case .validation(let m): return "validation: \(m)"
        case .server(let code, let m): return "server(\(code)): \(m)"
        case .transport(let e): return "transport: \(e)"
        }
    }

    /// The server's `detail` message alone, without the status prefix the case's string carries
    /// (e.g. "next: must be a path on this site…"), to show the user. Nil for a transport error.
    public var detail: String? {
        let message: String
        switch self {
        case .auth(let m), .notFound(let m), .tooLarge(let m), .validation(let m), .server(_, let m): message = m
        case .conflict(let m, _): message = m
        case .transport: return nil
        }
        guard let space = message.firstIndex(of: " "), Int(message[..<space]) != nil else { return message }
        return String(message[message.index(after: space)...])
    }

    /// On a refused route start (409), the uuid of the execution already running
    /// on that route — join it instead. Nil for any other error, including the
    /// other start 409 (client uuid already belongs to a different route).
    public var runningExecutionUuid: String? {
        guard case .conflict(_, let body) = self,
              let obj = try? JSONSerialization.jsonObject(with: body) as? [String: Any] else { return nil }
        return obj["running_execution_uuid"] as? String
    }
}
