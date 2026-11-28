import XCTest
@testable import Mechbase

final class DiagnosticsTests: ParityTestCase {
    func testCreateFindingFromCursor() async throws {
        reply("FindingOut", status: 201)
        _ = try await inst.findings.create(FindingInput(
            pointId: 3, pointSequence: 12, faultType: "bearing_outer", severity: "minor", dueBy: "2026-12-15",
            cursor: SpectrumCursor(hz: 87.5, amplitude: 1.2, unit: "mm/s", signal: "velocity", df: 0.25)))
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/findings/")
        XCTAssertEqual(json["point_id"] as? Int, 3)
        XCTAssertEqual(json["fault_type"] as? String, "bearing_outer")
        XCTAssertEqual(json["due_by"] as? String, "2026-12-15")
        XCTAssertEqual(json["hz"] as? Double, 87.5)
        XCTAssertEqual(json["df"] as? Double, 0.25)
        XCTAssertNil(json["shaft_hz"])
        XCTAssertEqual(json["recommended_action"] as? String, "")
    }

    func testFindingChoices() async throws {
        reply("FindingChoicesOut", nulls: true)
        let c = try await inst.findings.choices()
        XCTAssertEqual(url, "\(base)/findings/choices/")
        XCTAssertNil(c.suggestedFaultType)
        XCTAssertEqual(c.evidence, .object([:]))
        reply("FindingChoicesOut")
        let full = try await inst.findings.choices(pointId: 3, pointSequence: 12, cursor: SpectrumCursor(hz: 87.5, signal: "velocity"))
        XCTAssertEqual(url, "\(base)/findings/choices/?point_id=3&point_sequence=12&hz=87.5&signal=velocity")
        XCTAssertEqual(full.faultTypes.first?.value, "s")
    }

    func testBearings() async throws {
        reply("BearingListOut")
        let l = try await inst.bearings.list(query: "6205")
        XCTAssertEqual(url, "\(base)/bearings?q=6205")
        XCTAssertEqual(l.own.first?.match, "s")
        _ = try await inst.bearings.list(order: 3.58, sideband: "1x")
        XCTAssertEqual(url, "\(base)/bearings?order=3.58&sideband=1x")
        reply("BearingOut", nulls: true)
        let b = try await inst.bearings.get(uuid: u1)
        XCTAssertNil(b.rollingElements)
        XCTAssertEqual(url, "\(base)/bearings/\(u1)")
        _ = try await inst.bearings.create(BearingInput(designation: "X-1", rollingElements: 9, ballDiameter: 7.9, pitchDiameter: 39))
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(json["designation"] as? String, "X-1")
        XCTAssertEqual(json["rolling_elements"] as? Int, 9)
        XCTAssertNil(json["bpfo"])
        _ = try await inst.bearings.update(uuid: u1, BearingInput(contactAngle: 15))
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(json as? [String: Double], ["contact_angle": 15])
        ParityMock.reset(status: 404, reply: #"{"detail":"Not found"}"#)
        await expectError({ try await self.inst.bearings.delete(uuid: self.u1) }) {
            if case .notFound = $0 { return true }; return false
        }
        XCTAssertEqual(method, "DELETE")
    }
}
