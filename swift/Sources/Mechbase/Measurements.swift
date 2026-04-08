import Foundation

public struct Measurements: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    private struct CreateBody: Encodable {
        let measurement_point_id: Int
        let data: JSONValue
        let notes: String
        let session_id: String?
        let timestamp: String?
    }

    /// Create a new measurement (no file upload).
    public func create(
        pointId: Int,
        data: JSONValue,
        notes: String = "",
        sessionId: String? = nil,
        timestamp: String? = nil
    ) async throws -> Measurement {
        let body = CreateBody(
            measurement_point_id: pointId,
            data: data,
            notes: notes,
            session_id: sessionId,
            timestamp: timestamp
        )
        return try await scope.http.postJSON(
            scope.path("/measurements/"),
            body: body,
            as: Measurement.self
        )
    }

    /// Convenience overload accepting a `[String: Any]` data dictionary.
    public func create(
        pointId: Int,
        data: [String: Any],
        notes: String = "",
        sessionId: String? = nil,
        timestamp: String? = nil
    ) async throws -> Measurement {
        try await create(
            pointId: pointId,
            data: JSONValue.from(data),
            notes: notes,
            sessionId: sessionId,
            timestamp: timestamp
        )
    }

    /// Create a measurement with an attached file (multipart upload).
    public func create(
        pointId: Int,
        data: JSONValue,
        notes: String = "",
        sessionId: String? = nil,
        timestamp: String? = nil,
        fileURL: URL,
        mimeType: String = "application/octet-stream"
    ) async throws -> Measurement {
        let body = CreateBody(
            measurement_point_id: pointId,
            data: data,
            notes: notes,
            session_id: sessionId,
            timestamp: timestamp
        )
        let payloadJSON = try JSONEncoder().encode(body)
        let payloadStr = String(data: payloadJSON, encoding: .utf8) ?? "{}"
        let fileData = try Data(contentsOf: fileURL)
        return try await scope.http.postMultipart(
            scope.path("/measurements/upload/"),
            fields: ["payload": payloadStr],
            files: [(name: "file", filename: fileURL.lastPathComponent, mimeType: mimeType, data: fileData)],
            as: Measurement.self
        )
    }

    /// List measurements for a point.
    public func listForPoint(pointId: Int, limit: Int = 50, offset: Int = 0) async throws -> [Measurement] {
        let q = [
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        let page = try await scope.http.get(
            scope.path("/measurement-points/\(pointId)/measurements/"),
            query: q,
            as: Page<Measurement>.self
        )
        return page.items
    }
}
