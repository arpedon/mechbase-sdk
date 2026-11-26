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
        /// Analyst-confirmed thermal hotspots, top-level (the server strips it from
        /// `data`). nil is omitted → server runs detection; `[]` = analyst cleared.
        let hot_clusters: JSONValue?
    }

    private struct HotspotsBody: Encodable { let hot_clusters: [HotCluster] }

    /// Replace a measurement's thermal hotspots (full replacement; an empty array clears them).
    public func setHotspots(measurementUuid: String, hotClusters: [HotCluster]) async throws -> Measurement {
        try await scope.http.patchJSON(scope.path("/measurements/\(measurementUuid)/hotspots/"),
                                       body: HotspotsBody(hot_clusters: hotClusters), as: Measurement.self)
    }

    /// Create a new measurement (no file upload).
    public func create(
        pointId: Int,
        data: JSONValue,
        notes: String = "",
        sessionId: String? = nil,
        timestamp: String? = nil,
        hotClusters: JSONValue? = nil,
        idempotencyKey: String? = nil
    ) async throws -> Measurement {
        let body = CreateBody(
            measurement_point_id: pointId,
            data: data,
            notes: notes,
            session_id: sessionId,
            timestamp: timestamp,
            hot_clusters: hotClusters
        )
        return try await scope.http.postJSON(
            scope.path("/measurements/"),
            body: body,
            headers: idempotencyKey.map { ["X-Idempotency-Key": $0] } ?? [:],
            as: Measurement.self
        )
    }

    /// Convenience overload accepting a `[String: Any]` data dictionary.
    public func create(
        pointId: Int,
        data: [String: Any],
        notes: String = "",
        sessionId: String? = nil,
        timestamp: String? = nil,
        hotClusters: JSONValue? = nil,
        idempotencyKey: String? = nil
    ) async throws -> Measurement {
        try await create(
            pointId: pointId,
            data: JSONValue.from(data),
            notes: notes,
            sessionId: sessionId,
            timestamp: timestamp,
            hotClusters: hotClusters,
            idempotencyKey: idempotencyKey
        )
    }

    /// Create a measurement with an attached file (multipart upload).
    public func create(
        pointId: Int,
        data: JSONValue,
        notes: String = "",
        sessionId: String? = nil,
        timestamp: String? = nil,
        hotClusters: JSONValue? = nil,
        fileURL: URL,
        mimeType: String = "application/octet-stream",
        idempotencyKey: String? = nil
    ) async throws -> Measurement {
        let body = CreateBody(
            measurement_point_id: pointId,
            data: data,
            notes: notes,
            session_id: sessionId,
            timestamp: timestamp,
            hot_clusters: hotClusters
        )
        let payloadJSON = try JSONEncoder().encode(body)
        let payloadStr = String(data: payloadJSON, encoding: .utf8) ?? "{}"
        let fileData = try Data(contentsOf: fileURL)
        return try await scope.http.postMultipart(
            scope.path("/measurements/upload/"),
            fields: ["payload": payloadStr],
            files: [(name: "file", filename: fileURL.lastPathComponent, mimeType: mimeType, data: fileData)],
            headers: idempotencyKey.map { ["X-Idempotency-Key": $0] } ?? [:],
            as: Measurement.self
        )
    }

    /// List measurements for a point (offset pagination).
    public func listForPoint(pointId: Int, limit: Int = 50, offset: Int = 0,
                             createdFrom: String? = nil, createdTo: String? = nil) async throws -> [Measurement] {
        let q = [
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
            URLQueryItem(name: "created_from", value: createdFrom),
            URLQueryItem(name: "created_to", value: createdTo),
        ]
        return try await scope.http.get(
            scope.path("/measurement-points/\(pointId)/measurements/"),
            query: q, as: Page<Measurement>.self).items
    }
}

/// One item in a measurement batch. Supply exactly one of pointId / pointExternalId.
public struct MeasurementInput: Encodable, Sendable {
    public var measurementPointId: Int?
    public var measurementPointExternalId: String?
    public var data: JSONValue
    public var notes: String?
    public var sessionId: String?
    public var timestamp: String?
    public var externalId: String?

    public init(measurementPointId: Int? = nil, measurementPointExternalId: String? = nil,
                data: JSONValue, notes: String? = nil, sessionId: String? = nil,
                timestamp: String? = nil, externalId: String? = nil) {
        self.measurementPointId = measurementPointId
        self.measurementPointExternalId = measurementPointExternalId
        self.data = data
        self.notes = notes
        self.sessionId = sessionId
        self.timestamp = timestamp
        self.externalId = externalId
    }

    public init(measurementPointId: Int? = nil, measurementPointExternalId: String? = nil,
                data: [String: Any], notes: String? = nil, sessionId: String? = nil,
                timestamp: String? = nil, externalId: String? = nil) {
        self.init(measurementPointId: measurementPointId,
                  measurementPointExternalId: measurementPointExternalId,
                  data: JSONValue.from(data), notes: notes, sessionId: sessionId,
                  timestamp: timestamp, externalId: externalId)
    }

    enum CodingKeys: String, CodingKey {
        case data, notes, timestamp
        case measurementPointId = "measurement_point_id"
        case measurementPointExternalId = "measurement_point_external_id"
        case sessionId = "session_id"
        case externalId = "external_id"
    }
}

public extension Measurements {
    private struct BatchBody: Encodable { let items: [MeasurementInput] }

    /// Push many measurements in one request.
    func createBatch(_ items: [MeasurementInput]) async throws -> BatchResult {
        try await scope.http.postJSON(scope.path("/measurements/batch/"),
                                      body: BatchBody(items: items), as: BatchResult.self)
    }

    /// Attach a file to an existing measurement (multipart). Pass a client-minted
    /// `uuid` so a retry after a lost reply returns the same file instead of a duplicate.
    func addFile(measurementUUID: String, fileURL: URL,
                 mimeType: String = "application/octet-stream",
                 uuid: String? = nil) async throws -> FileAttachment {
        let data = try Data(contentsOf: fileURL)
        return try await scope.http.postMultipart(
            scope.path("/measurements/\(measurementUUID)/files/"),
            fields: uuid.map { ["uuid": $0] } ?? [:],
            files: [(name: "file", filename: fileURL.lastPathComponent, mimeType: mimeType, data: data)],
            as: FileAttachment.self)
    }

    /// Stream the full history for a point, following cursor pages.
    func iterForPoint(pointId: Int, createdFrom: String? = nil, createdTo: String? = nil,
                      pageSize: Int = 100) -> AsyncThrowingStream<Measurement, Error> {
        let scope = self.scope
        return AsyncThrowingStream { continuation in
            Task {
                var cursor: String? = ""
                do {
                    while !Task.isCancelled {
                        let q: [URLQueryItem] = [
                            URLQueryItem(name: "cursor", value: cursor ?? ""),
                            URLQueryItem(name: "limit", value: String(pageSize)),
                            URLQueryItem(name: "created_from", value: createdFrom),
                            URLQueryItem(name: "created_to", value: createdTo),
                        ]
                        let page = try await scope.http.get(
                            scope.path("/measurement-points/\(pointId)/measurements/"),
                            query: q, stripEmpty: false, as: CursorPage<Measurement>.self)
                        for m in page.items { continuation.yield(m) }
                        guard let next = page.nextCursor, !next.isEmpty else { break }
                        cursor = next
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }
}

/// An analyst-confirmed thermal hotspot; coordinates are percentages of the frame,
/// `severity` a status int, `source` `auto` or `manual`.
public struct HotCluster: Codable, Sendable, Equatable {
    public let cxPct: Double
    public let cyPct: Double
    public let maxTempC: Double
    public let deltaTC: Double
    public let severity: Int
    public let source: String?

    public init(cxPct: Double, cyPct: Double, maxTempC: Double, deltaTC: Double, severity: Int, source: String? = nil) {
        self.cxPct = cxPct; self.cyPct = cyPct; self.maxTempC = maxTempC
        self.deltaTC = deltaTC; self.severity = severity; self.source = source
    }

    enum CodingKeys: String, CodingKey {
        case severity, source
        case cxPct = "cx_pct", cyPct = "cy_pct", maxTempC = "max_temp_c", deltaTC = "delta_t_c"
    }
}
