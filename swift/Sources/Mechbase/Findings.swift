import Foundation

/// One analyst finding, flat for a CMMS; `*ExternalId`s are the caller-owned keys a sync matches on.
public struct Finding: Codable, Sendable {
    public let uuid: String
    public let status: String
    public let faultType: String
    public let faultTypeDisplay: String
    public let severity: String
    public let recommendedAction: String
    public let dueBy: String?
    public let comment: String
    public let evidence: JSONValue
    public let workOrderRef: String
    public let acknowledgedAt: String?
    public let closedAt: String?
    public let createdAt: String
    public let updatedAt: String
    public let createdBy: String?
    public let assetId: Int?
    public let assetExternalId: String?
    public let assetName: String
    public let pointId: Int?
    public let pointExternalId: String?
    public let pointName: String
    public let pointLocation: String
    public let measurementUuid: String?
    public let measurementExternalId: String?
    public let measurementTimestamp: String?
    public let webUrl: String

    enum CodingKeys: String, CodingKey {
        case uuid, status, severity, comment, evidence
        case faultType = "fault_type", faultTypeDisplay = "fault_type_display"
        case recommendedAction = "recommended_action", dueBy = "due_by"
        case workOrderRef = "work_order_ref", acknowledgedAt = "acknowledged_at", closedAt = "closed_at"
        case createdAt = "created_at", updatedAt = "updated_at", createdBy = "created_by"
        case assetId = "asset_id", assetExternalId = "asset_external_id", assetName = "asset_name"
        case pointId = "point_id", pointExternalId = "point_external_id"
        case pointName = "point_name", pointLocation = "point_location"
        case measurementUuid = "measurement_uuid", measurementExternalId = "measurement_external_id"
        case measurementTimestamp = "measurement_timestamp", webUrl = "web_url"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func str(_ k: CodingKeys) -> String { (try? c.decode(String.self, forKey: k)) ?? "" }
        self.uuid = try c.decode(String.self, forKey: .uuid)
        self.status = try c.decode(String.self, forKey: .status)
        self.faultType = str(.faultType)
        self.faultTypeDisplay = str(.faultTypeDisplay)
        self.severity = str(.severity)
        self.recommendedAction = str(.recommendedAction)
        self.dueBy = try c.decodeIfPresent(String.self, forKey: .dueBy)
        self.comment = str(.comment)
        self.evidence = (try? c.decode(JSONValue.self, forKey: .evidence)) ?? .object([:])
        self.workOrderRef = str(.workOrderRef)
        self.acknowledgedAt = try c.decodeIfPresent(String.self, forKey: .acknowledgedAt)
        self.closedAt = try c.decodeIfPresent(String.self, forKey: .closedAt)
        self.createdAt = try c.decode(String.self, forKey: .createdAt)
        self.updatedAt = try c.decode(String.self, forKey: .updatedAt)
        self.createdBy = try c.decodeIfPresent(String.self, forKey: .createdBy)
        self.assetId = try c.decodeIfPresent(Int.self, forKey: .assetId)
        self.assetExternalId = try c.decodeIfPresent(String.self, forKey: .assetExternalId)
        self.assetName = str(.assetName)
        self.pointId = try c.decodeIfPresent(Int.self, forKey: .pointId)
        self.pointExternalId = try c.decodeIfPresent(String.self, forKey: .pointExternalId)
        self.pointName = str(.pointName)
        self.pointLocation = str(.pointLocation)
        self.measurementUuid = try c.decodeIfPresent(String.self, forKey: .measurementUuid)
        self.measurementExternalId = try c.decodeIfPresent(String.self, forKey: .measurementExternalId)
        self.measurementTimestamp = try c.decodeIfPresent(String.self, forKey: .measurementTimestamp)
        self.webUrl = str(.webUrl)
    }
}

/// One page of findings; pass `nextCursor` back as `cursor` until it is `nil`.
public struct FindingsPage: Codable, Sendable {
    public let items: [Finding]
    public let nextCursor: String?
    enum CodingKeys: String, CodingKey { case items; case nextCursor = "next_cursor" }
}

public final class Findings: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    /// `status` is `open`, `acknowledged` or `closed`; `since` an ISO 8601 datetime.
    public func list(cursor: String? = nil, limit: Int? = nil, since: String? = nil, status: String? = nil,
                     assetId: Int? = nil, assetExternalId: String? = nil,
                     pointId: Int? = nil, pointExternalId: String? = nil) async throws -> FindingsPage {
        let q = [
            URLQueryItem(name: "cursor", value: cursor),
            URLQueryItem(name: "limit", value: limit.map(String.init)),
            URLQueryItem(name: "since", value: since),
            URLQueryItem(name: "status", value: status),
            URLQueryItem(name: "asset_id", value: assetId.map(String.init)),
            URLQueryItem(name: "asset_external_id", value: assetExternalId),
            URLQueryItem(name: "point_id", value: pointId.map(String.init)),
            URLQueryItem(name: "point_external_id", value: pointExternalId),
        ]
        return try await scope.http.get(scope.path("/findings/"), query: q, as: FindingsPage.self)
    }

    public func get(uuid: String) async throws -> Finding {
        try await scope.http.get(scope.path("/findings/\(uuid)/"), as: Finding.self)
    }

    private struct StatusBody: Encodable { let status: String; let work_order_ref: String? }

    /// Move a finding on: `acknowledged` (a work order was raised; `workOrderRef` required) or `closed`.
    public func setStatus(uuid: String, status: String, workOrderRef: String? = nil) async throws -> Finding {
        try await scope.http.postJSON(scope.path("/findings/\(uuid)/status/"),
                                      body: StatusBody(status: status, work_order_ref: workOrderRef), as: Finding.self)
    }
}
