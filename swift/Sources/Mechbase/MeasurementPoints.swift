import Foundation

/// Create/upsert/update body for measurement points. Nil fields are omitted by the encoder.
public struct PointInput: Encodable, Sendable {
    public var name: String?
    public var externalId: String?
    public var assetId: Int?
    public var assetExternalId: String?
    public var transducerType: String?
    public var measurementUnitCode: String?
    public var location: String?
    public var bodySegment: Int?
    public var bodyAngle: Int?
    public var machineClass: String?

    public init(name: String? = nil, externalId: String? = nil, assetId: Int? = nil,
                assetExternalId: String? = nil, transducerType: String? = nil,
                measurementUnitCode: String? = nil, location: String? = nil,
                bodySegment: Int? = nil, bodyAngle: Int? = nil, machineClass: String? = nil) {
        self.name = name
        self.externalId = externalId
        self.assetId = assetId
        self.assetExternalId = assetExternalId
        self.transducerType = transducerType
        self.measurementUnitCode = measurementUnitCode
        self.location = location
        self.bodySegment = bodySegment
        self.bodyAngle = bodyAngle
        self.machineClass = machineClass
    }

    enum CodingKeys: String, CodingKey {
        case name, location
        case externalId = "external_id"
        case assetId = "asset_id"
        case assetExternalId = "asset_external_id"
        case transducerType = "transducer_type"
        case measurementUnitCode = "measurement_unit_code"
        case bodySegment = "body_segment"
        case bodyAngle = "body_angle"
        case machineClass = "machine_class"
    }
}

public struct MeasurementPoints: Sendable {
    let scope: InstallationScope

    init(http: HTTPClient, installationId: Int) {
        self.scope = InstallationScope(http: http, installationId: installationId)
    }

    public func list(
        query: String? = nil,
        assetId: Int? = nil,
        transducerType: String? = nil,
        limit: Int = 50,
        offset: Int = 0
    ) async throws -> [MeasurementPoint] {
        let q: [URLQueryItem] = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "asset_id", value: assetId.map(String.init)),
            URLQueryItem(name: "transducer_type", value: transducerType),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        let page = try await scope.http.get(
            scope.path("/measurement-points"),
            query: q,
            as: Page<MeasurementPoint>.self
        )
        return page.items
    }

    public func get(id: Int) async throws -> MeasurementPoint {
        try await scope.http.get(scope.path("/measurement-points/\(id)"), as: MeasurementPoint.self)
    }

    public func create(_ input: PointInput) async throws -> MeasurementPoint {
        try await scope.http.postJSON(scope.path("/measurement-points"), body: input, as: MeasurementPoint.self)
    }

    public func upsert(_ input: PointInput) async throws -> MeasurementPoint {
        try await scope.http.putJSON(scope.path("/measurement-points"), body: input, as: MeasurementPoint.self)
    }

    public func update(id: Int, _ input: PointInput) async throws -> MeasurementPoint {
        try await scope.http.patchJSON(scope.path("/measurement-points/\(id)"), body: input, as: MeasurementPoint.self)
    }

    public func delete(id: Int, cascade: Bool = false) async throws -> DeleteResult {
        let q = cascade ? [URLQueryItem(name: "cascade", value: "true")] : []
        return try await scope.http.delete(scope.path("/measurement-points/\(id)"), query: q, as: DeleteResult.self)
    }
}
