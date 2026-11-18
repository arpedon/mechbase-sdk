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

    /// Run state, staleness, limits and the last 7 days for one point.
    public func context(pointId: Int) async throws -> PointContext {
        try await scope.http.get(scope.path("/measurement-points/\(pointId)/context"), as: PointContext.self)
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

    /// Add a photo to the point's gallery; it never changes the reference photo (see ``setReferencePhoto(pointId:uuid:)``; a point with none falls back to its first photo). Pass a client-minted `uuid` so a retry returns the same photo.
    public func addPhoto(pointId: Int, fileURL: URL, mimeType: String = "image/jpeg",
                         uuid: String? = nil) async throws -> FileAttachment {
        let data = try Data(contentsOf: fileURL)
        return try await scope.http.postMultipart(
            scope.path("/measurement-points/\(pointId)/photos/"),
            fields: uuid.map { ["uuid": $0] } ?? [:],
            files: [(name: "file", filename: fileURL.lastPathComponent, mimeType: mimeType, data: data)],
            as: FileAttachment.self)
    }

    /// Delete a gallery photo by its ``Photo/uuid``. A photo that's already gone throws ``MechbaseError/notFound(_:)``; a non-UUID `uuid` throws ``MechbaseError/validation(_:)`` without a request.
    public func deletePhoto(pointId: Int, uuid: String) async throws {
        // Interpolated into the path: anything but a UUID could reroute or truncate it.
        guard UUID(uuidString: uuid) != nil else { throw MechbaseError.validation("invalid photo uuid: \(uuid)") }
        _ = try await scope.http.delete(scope.path("/measurement-points/\(pointId)/photos/\(uuid)"), as: EmptyResponse.self)
    }

    /// Make the gallery photo `uuid` (a ``Photo/uuid``) the point's reference photo; returns the updated point. A photo or point that's gone throws ``MechbaseError/notFound(_:)``; a non-UUID `uuid` throws ``MechbaseError/validation(_:)`` without a request.
    public func setReferencePhoto(pointId: Int, uuid: String) async throws -> MeasurementPoint {
        guard UUID(uuidString: uuid) != nil else { throw MechbaseError.validation("invalid photo uuid: \(uuid)") }
        return try await scope.http.putJSON(scope.path("/measurement-points/\(pointId)/reference-photo"),
                                            body: ["uuid": uuid], as: MeasurementPoint.self)
    }
}
