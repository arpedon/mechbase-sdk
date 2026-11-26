import Foundation

/// Optional export filters; unset ones are omitted. Datetimes are ISO 8601.
public struct ExportFilters: Codable, Sendable {
    public var assetId: Int?
    public var assetExternalId: String?
    public var pointId: Int?
    public var pointExternalId: String?
    public var transducerType: String?
    public var status: String?
    public var action: String?
    public var routeId: String?
    public var createdFrom: String?
    public var createdTo: String?
    public var updatedSince: String?

    public init(assetId: Int? = nil, assetExternalId: String? = nil, pointId: Int? = nil,
                pointExternalId: String? = nil, transducerType: String? = nil, status: String? = nil,
                action: String? = nil, routeId: String? = nil, createdFrom: String? = nil,
                createdTo: String? = nil, updatedSince: String? = nil) {
        self.assetId = assetId; self.assetExternalId = assetExternalId; self.pointId = pointId
        self.pointExternalId = pointExternalId; self.transducerType = transducerType; self.status = status
        self.action = action; self.routeId = routeId; self.createdFrom = createdFrom
        self.createdTo = createdTo; self.updatedSince = updatedSince
    }

    enum CodingKeys: String, CodingKey {
        case status, action
        case assetId = "asset_id", assetExternalId = "asset_external_id"
        case pointId = "point_id", pointExternalId = "point_external_id"
        case transducerType = "transducer_type", routeId = "route_id"
        case createdFrom = "created_from", createdTo = "created_to", updatedSince = "updated_since"
    }
}

/// A queued export (202). Poll ``Exports/status(jobUuid:)`` until `state` is done.
public struct ExportJob: Codable, Sendable, Equatable {
    public let jobUuid: String
    public let state: String
    public let statusUrl: String
    enum CodingKeys: String, CodingKey {
        case state
        case jobUuid = "job_uuid", statusUrl = "status_url"
    }
}

public struct ExportStatus: Codable, Sendable, Equatable {
    public let jobUuid: String
    public let dataset: String
    public let fileFormat: String
    public let state: String
    public let rowCount: Int?
    public let byteSize: Int?
    public let downloadUrl: String?
    public let expiresAt: String?
    public let error: String
    public let createdAt: String

    enum CodingKeys: String, CodingKey {
        case dataset, state, error
        case jobUuid = "job_uuid", fileFormat = "file_format", rowCount = "row_count"
        case byteSize = "byte_size", downloadUrl = "download_url", expiresAt = "expires_at"
        case createdAt = "created_at"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.jobUuid = try c.decode(String.self, forKey: .jobUuid)
        self.dataset = try c.decode(String.self, forKey: .dataset)
        self.fileFormat = try c.decode(String.self, forKey: .fileFormat)
        self.state = try c.decode(String.self, forKey: .state)
        self.rowCount = try c.decodeIfPresent(Int.self, forKey: .rowCount)
        self.byteSize = try c.decodeIfPresent(Int.self, forKey: .byteSize)
        self.downloadUrl = try c.decodeIfPresent(String.self, forKey: .downloadUrl)
        self.expiresAt = try c.decodeIfPresent(String.self, forKey: .expiresAt)
        self.error = (try? c.decode(String.self, forKey: .error)) ?? ""
        self.createdAt = try c.decode(String.self, forKey: .createdAt)
    }
}

/// Bulk analytics exports (asynchronous: create, poll, download).
public final class Exports: Sendable {
    private let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    private struct CreateBody: Encodable { let dataset: String; let format: String; let filters: ExportFilters }

    public func create(dataset: String, format: String = "csv", filters: ExportFilters = ExportFilters()) async throws -> ExportJob {
        try await scope.http.postJSON(scope.path("/analytics/exports/"),
                                      body: CreateBody(dataset: dataset, format: format, filters: filters), as: ExportJob.self)
    }

    public func status(jobUuid: String) async throws -> ExportStatus {
        try await scope.http.get(scope.path("/analytics/exports/\(jobUuid)/"), as: ExportStatus.self)
    }

    /// The finished file's raw bytes. Reads the signed link from ``status(jobUuid:)``, so the job must be done.
    public func download(jobUuid: String) async throws -> Data {
        let st = try await status(jobUuid: jobUuid)
        guard let link = st.downloadUrl else { throw MechbaseError.server(410, "Export \(jobUuid) has no file yet (\(st.state))") }
        // Keep only the signature; the path resolves against the client's base URL.
        let sig = URLComponents(string: link)?.queryItems?.first { $0.name == "sig" }?.value
        return try await scope.http.getData(scope.path("/analytics/exports/\(jobUuid)/download/"),
                                            query: [URLQueryItem(name: "sig", value: sig)])
    }
}
