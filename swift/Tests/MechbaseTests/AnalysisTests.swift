import XCTest
@testable import Mechbase

final class AnalysisTests: ParityTestCase {
    func testReadingAnalysisQueryAndDecode() async throws {
        reply("ReadingAnalysisOut")
        let a = try await inst.measurements.analysis(pointId: 3, pointSequence: 12, highpassHz: 10, lowpassHz: 1000)
        XCTAssertEqual(method, "GET")
        XCTAssertEqual(url, "\(base)/measurement-points/3/measurements/12/analysis?highpass_hz=10.0&lowpass_hz=1000.0")
        XCTAssertEqual(a.vibration?.waveform?.accel.tS, [1.5])
        XCTAssertEqual(a.vibration?.thresholds["velocity"]?.x, [1.5])
        XCTAssertEqual(a.units.frequencyScale, 1.5)
        XCTAssertEqual(a.thermography?.thermograms.first?.hotClusters.first?.severity, 2)
    }

    func testReadingAnalysisNullsAndDefaults() async throws {
        reply("ReadingAnalysisOut", nulls: true)
        let a = try await inst.measurements.analysis(pointId: 3, pointSequence: 12)
        XCTAssertEqual(url, "\(base)/measurement-points/3/measurements/12/analysis")
        XCTAssertNil(a.vibration)
        XCTAssertNil(a.source)
        // A vibration block that leaves the defaulted fields out.
        let v = try JSONDecoder().decode(Vibration.self, from: Data(#"{"spectrum":{"freq_hz":[],"accel":[],"velocity":[],"envelope":[],"n_source":0},"thresholds":{},"bearing_markers":[]}"#.utf8))
        XCTAssertEqual(v.nLines, 0)
        XCTAssertEqual(v.sourceResolutionHz, 0)
        XCTAssertNil(v.waveform)
    }

    func testFilterOutOfBandIsValidationError() async {
        ParityMock.reset(status: 422, reply: #"{"detail":"highpass_hz: must lie in (0, fs/2)"}"#)
        await expectError({ _ = try await self.inst.measurements.analysis(pointId: 3, pointSequence: 1, highpassHz: -1) }) {
            if case .validation = $0 { return true }; return false
        }
    }

    func testProcessBody() async throws {
        reply("ProcessOut")
        let r = try await inst.measurements.process(pointId: 3, pointSequence: 12,
                                                     ProcessInput(type: "envelope", highPass: 500, peakCount: 5, cursors: [12, 11]))
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/measurement-points/3/measurements/12/process")
        XCTAssertEqual(json["type"] as? String, "envelope")
        XCTAssertEqual(json["high_pass"] as? Double, 500)
        XCTAssertEqual(json["low_pass"] as? Double, 0)
        XCTAssertEqual(json["db_scale"] as? Bool, false)
        XCTAssertEqual(json["peak_count"] as? Int, 5)
        XCTAssertEqual(json["cursors"] as? [Int], [12, 11])
        XCTAssertEqual(r.cursors.first?.peaks.first?.x, 1.5)
        reply("ProcessOut", nulls: true)
        let got = try await inst.measurements.process(pointId: 3, pointSequence: 12)
        XCTAssertEqual(got.cursors.first?.peaks.count, 0)  // absent: the default
    }

    func testCompareConditional() async throws {
        reply("CompareOut")
        ParityMock.headers = ["ETag": #""e1""#]
        let r = try await inst.measurementPoints.compare(pointId: 3, pointSequences: [12, 11], spectrum: "envelope")
        XCTAssertEqual(url, "\(base)/measurement-points/3/compare?seq=12%2C11&spectrum=envelope")
        XCTAssertEqual(r.etag, #""e1""#)
        XCTAssertEqual(r.value?.cursors.first?.markers.first?.kind, "s")
        ParityMock.reset(status: 304, reply: "")
        let again = try await inst.measurementPoints.compare(pointId: 3, pointSequences: [12, 11], etag: #""e1""#)
        XCTAssertEqual(header("If-None-Match"), #""e1""#)
        XCTAssertNil(again.value)
        ParityMock.reset(status: 422, reply: #"{"detail":"seq: at most 8"}"#)
        await expectError({ _ = try await self.inst.measurementPoints.compare(pointId: 3, pointSequences: Array(1...9)) }) {
            if case .validation = $0 { return true }; return false
        }
    }

    func testNotesTrendFaultRecord() async throws {
        reply("MeasurementOut")
        _ = try await inst.measurements.updateNotes(pointId: 3, pointSequence: 12, notes: "<p>loose</p>")
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(url, "\(base)/measurement-points/3/measurements/12/")
        XCTAssertEqual(json as? [String: String], ["notes": "<p>loose</p>"])
        reply("TrendOut")
        let t = try await inst.assets.trend(assetId: 5, type: "VB")
        XCTAssertEqual(url, "\(base)/assets/5/trend?type=VB")
        XCTAssertEqual(t.series.first?.measurements.first?.off, true)
        XCTAssertEqual(t.series.first?.thresholds?.direction, "s")
        reply("FaultRecordOut", nulls: true)
        let f = try await inst.assets.faultRecord(assetId: 5, at: "2026-11-27T10:00:00+02:00", pointId: 8)
        XCTAssertEqual(url, "\(base)/assets/5/fault-record?at=2026-11-27T10%3A00%3A00%2B02%3A00&point=8")
        XCTAssertNil(f.triggerPointId)
        XCTAssertEqual(f.rows.first?.series.count, 0)
    }

    func testBaselines() async throws {
        reply("BaselineOut", status: 202)
        _ = try await inst.measurementPoints.createBaseline(pointId: 3, refitFrom: "2026-10-01")
        XCTAssertEqual(method, "POST")
        XCTAssertEqual(url, "\(base)/measurement-points/3/baseline")
        XCTAssertEqual(json as? [String: String], ["refit_from": "2026-10-01"])
        _ = try await inst.measurementPoints.clearBaseline(pointId: 3)
        XCTAssertEqual(method, "DELETE")
        reply("BaselinePreviewOut")
        let p = try await inst.measurementPoints.baselinePreview(pointId: 3, since: "2026-10-01")
        XCTAssertEqual(url, "\(base)/measurement-points/3/baseline/preview?since=2026-10-01")
        XCTAssertEqual(p.fitMin, 2)
    }

    func testPointAnalysisFields() async throws {
        reply("MeasurementPointOut")
        let p = try await inst.measurementPoints.get(id: 3)
        XCTAssertEqual(p.bearing, "6f1c0000-0000-4000-8000-00000000000a")
        XCTAssertEqual(p.speedRatio, 1.5)
        XCTAssertTrue(p.hasOwnInstructions)
        reply("MeasurementPointOut", nulls: true)
        let n = try await inst.measurementPoints.get(id: 3)
        XCTAssertNil(n.nominalRpm)
        XCTAssertEqual(n.speedRatio, 1)
        XCTAssertFalse(n.hasOwnInstructions)
        // nil omits, .some(nil) sends null.
        _ = try await inst.measurementPoints.update(id: 3, PointInput(nominalRpm: 1480, bearing: .some(nil), instructions: ""))
        XCTAssertEqual(method, "PATCH")
        XCTAssertEqual(json["nominal_rpm"] as? Int, 1480)
        XCTAssertTrue(json["bearing"] is NSNull)
        XCTAssertNil(json["speed_ratio"])
        XCTAssertEqual(json["instructions"] as? String, "")
    }
}
