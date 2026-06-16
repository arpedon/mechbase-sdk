import Foundation

/// Errors thrown by the Mechbase SDK.
public enum MechbaseError: Error, CustomStringConvertible {
    /// 401 / 403.
    case auth(String)
    /// 404.
    case notFound(String)
    /// 409.
    case conflict(String)
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
        case .conflict(let m): return "conflict: \(m)"
        case .tooLarge(let m): return "tooLarge: \(m)"
        case .validation(let m): return "validation: \(m)"
        case .server(let code, let m): return "server(\(code)): \(m)"
        case .transport(let e): return "transport: \(e)"
        }
    }
}
