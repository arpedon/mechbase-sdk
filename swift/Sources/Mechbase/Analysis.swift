import Foundation

// Reading analysis (what the web reading page draws), compare, asset trend, fault record, baselines.
// Arrays are in the response's `units` (the viewer's preferences); frequencies are always Hz.

/// The compare panel's processing for ``Measurements/process(pointId:pointSequence:_:)``.
public struct ProcessInput: Encodable, Sendable {
    /// accel | velocity | envelope | waveform (x in ms).
    public var type: String
    /// Hz; 0 = none.
    public var highPass: Double
    public var lowPass: Double
    public var dbScale: Bool
    public var peakCount: Int
    /// Up to 8 point_sequences of the same point; empty = this reading alone.
    public var cursors: [Int]

    public init(type: String = "velocity", highPass: Double = 0, lowPass: Double = 0, dbScale: Bool = false,
                peakCount: Int = 0, cursors: [Int] = []) {
        self.type = type
        self.highPass = highPass
        self.lowPass = lowPass
        self.dbScale = dbScale
        self.peakCount = peakCount
        self.cursors = cursors
    }

    enum CodingKeys: String, CodingKey {
        case type, cursors
        case highPass = "high_pass", lowPass = "low_pass", dbScale = "db_scale", peakCount = "peak_count"
    }
}

extension Measurements {
    private func readingPath(_ pointId: Int, _ seq: Int, _ suffix: String) -> String {
        scope.path("/measurement-points/\(pointId)/measurements/\(seq)\(suffix)")
    }

    /// Waveforms (plot `values[i]` at `tS[i]`), spectra, bearing markers, thresholds, order and
    /// thermography for one reading. The band-pass filters reprocess the waveform (each in (0, fs/2),
    /// high below low, else 422).
    public func analysis(pointId: Int, pointSequence: Int, highpassHz: Double? = nil,
                         lowpassHz: Double? = nil) async throws -> ReadingAnalysis {
        let q = [URLQueryItem(name: "highpass_hz", value: highpassHz.map { String($0) }),
                 URLQueryItem(name: "lowpass_hz", value: lowpassHz.map { String($0) })]
        return try await scope.http.get(readingPath(pointId, pointSequence, "/analysis"), query: q,
                                        as: ReadingAnalysis.self)
    }

    /// Run the compare panel's processing over this reading or `input.cursors`. A foreign or missing
    /// cursor comes back with empty arrays.
    public func process(pointId: Int, pointSequence: Int, _ input: ProcessInput = ProcessInput()) async throws -> ProcessResult {
        try await scope.http.postJSON(readingPath(pointId, pointSequence, "/process"), body: input, as: ProcessResult.self)
    }

    private struct NotesBody: Encodable { let notes: String }

    /// Replace a reading's notes (rich-text HTML, sanitized server-side).
    public func updateNotes(pointId: Int, pointSequence: Int, notes: String) async throws -> Measurement {
        try await scope.http.patchJSON(readingPath(pointId, pointSequence, "/"), body: NotesBody(notes: notes),
                                       as: Measurement.self)
    }
}

extension MeasurementPoints {
    /// Overlay spectra of up to 8 readings of the point (`spectrum`: accel | velocity | envelope).
    /// Conditional: pass the last ETag to get `.notModified`.
    public func compare(pointId: Int, pointSequences: [Int], spectrum: String = "velocity",
                        etag: String? = nil) async throws -> Conditional<CompareResult> {
        guard !pointSequences.isEmpty else { throw MechbaseError.validation("compare needs at least one point_sequence") }
        let q = [URLQueryItem(name: "seq", value: pointSequences.map(String.init).joined(separator: ",")),
                 URLQueryItem(name: "spectrum", value: spectrum)]
        return try await scope.http.getConditional(scope.path("/measurement-points/\(pointId)/compare"), query: q,
                                                   etag: etag, as: CompareResult.self)
    }

    private struct BaselineBody: Encodable { let refit_from: String }

    /// Queue the baseline fit over readings on and after `refitFrom` (`YYYY-MM-DD`). 422 with fewer
    /// than ``BaselinePreview/fitMin`` usable readings.
    public func createBaseline(pointId: Int, refitFrom: String) async throws -> BaselineResult {
        try await scope.http.postJSON(scope.path("/measurement-points/\(pointId)/baseline"),
                                      body: BaselineBody(refit_from: refitFrom), as: BaselineResult.self)
    }

    /// Remove the point's operating modes and baselines (back to the ISO limits).
    public func clearBaseline(pointId: Int) async throws -> BaselineResult {
        try await scope.http.delete(scope.path("/measurement-points/\(pointId)/baseline"), as: BaselineResult.self)
    }

    /// How many usable readings a fit from `since` (`YYYY-MM-DD`) would get.
    public func baselinePreview(pointId: Int, since: String? = nil) async throws -> BaselinePreview {
        try await scope.http.get(scope.path("/measurement-points/\(pointId)/baseline/preview"),
                                 query: [URLQueryItem(name: "since", value: since)], as: BaselinePreview.self)
    }
}

extension Assets {
    /// The asset chart: one series per non-Production point over the 7 days before its latest reading,
    /// plus the Production on/off samples. `type` narrows to one transducer type.
    public func trend(assetId: Int, type: String? = nil) async throws -> AssetTrend {
        try await scope.http.get(scope.path("/assets/\(assetId)/trend"), query: [URLQueryItem(name: "type", value: type)],
                                 as: AssetTrend.self)
    }

    /// Every scalar point's readings within 60 s of `at` (ISO 8601), native units. `pointId` names the
    /// point that raised the change.
    public func faultRecord(assetId: Int, at: String, pointId: Int? = nil) async throws -> FaultRecord {
        try await scope.http.get(scope.path("/assets/\(assetId)/fault-record"),
                                 query: [URLQueryItem(name: "at", value: at),
                                         URLQueryItem(name: "point", value: pointId.map(String.init))],
                                 as: FaultRecord.self)
    }
}

public struct ReadingAnalysis: Codable, Sendable {
    public let uuid: String
    public let pointId: Int
    public let pointSequence: Int
    public let createdAt: String
    public let status: String
    public let notes: String
    public let transducerType: String
    /// How it arrived: "MQTT", "Route", "Manual", or null.
    public let source: String?
    public let previousSequence: Int?
    public let nextSequence: Int?
    /// Scalar values in their native units.
    public let data: JSONValue
    /// Per data key: display = native * scale + offset.
    public let displayUnits: [String: DisplayUnit]
    public let units: AnalysisUnits
    public let filter: AnalysisFilter?
    public let vibration: Vibration?
    public let thermography: Thermography?
    public let attachments: [FileAttachment]
    enum CodingKeys: String, CodingKey {
        case uuid, status, notes, source, data, units, filter, vibration, thermography, attachments
        case pointId = "point_id", pointSequence = "point_sequence", createdAt = "created_at"
        case transducerType = "transducer_type", previousSequence = "previous_sequence"
        case nextSequence = "next_sequence", displayUnits = "display_units"
    }
}

/// The units the arrays in this response are in: the viewer's preferences.
public struct AnalysisUnits: Codable, Sendable {
    /// Acceleration waveform/spectrum and envelope arrays (native g).
    public let acceleration: String
    /// Velocity arrays, 1X/2X amplitudes and one-rev views (native mm/s).
    public let velocity: String
    /// Thermogram temperatures (native °C). Deltas scale without offset.
    public let temperature: String
    /// Preferred frequency DISPLAY unit. Frequency arrays are always Hz.
    public let frequency: String
    /// display = hz * frequency_scale (60 for CPM).
    public let frequencyScale: Double
    enum CodingKeys: String, CodingKey {
        case acceleration, velocity, temperature, frequency
        case frequencyScale = "frequency_scale"
    }
}

public struct AnalysisFilter: Codable, Sendable {
    public let highpassHz: Double?
    public let lowpassHz: Double?
    enum CodingKeys: String, CodingKey {
        case highpassHz = "highpass_hz", lowpassHz = "lowpass_hz"
    }
}

public struct Vibration: Codable, Sendable {
    public let fs: Double?
    /// Lines in the returned (thinned) spectrum.
    public let nLines: Int
    /// Line spacing of the returned spectrum, Hz.
    public let freqResolutionHz: Double
    /// The FFT's own bin width before thinning, Hz.
    public let sourceResolutionHz: Double
    public let fmaxHz: Double?
    public let envBandHz: [Double]?
    /// None for a legacy reading with spectra but no .dr.
    public let waveform: Waveforms?
    public let spectrum: Spectrum
    /// Keyed by "accel" / "velocity" / "envelope".
    public let thresholds: [String: Staircase]
    public let bearingMarkers: [FrequencyMarker]
    public let order: OrderAnalysis?
    enum CodingKeys: String, CodingKey {
        case fs, waveform, spectrum, thresholds, order
        case nLines = "n_lines", freqResolutionHz = "freq_resolution_hz"
        case sourceResolutionHz = "source_resolution_hz", fmaxHz = "fmax_hz", envBandHz = "env_band_hz"
        case bearingMarkers = "bearing_markers"
    }
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.fs = try c.decodeIfPresent(Double.self, forKey: .fs)
        self.nLines = try c.decodeIfPresent(Int.self, forKey: .nLines) ?? 0
        self.freqResolutionHz = try c.decodeIfPresent(Double.self, forKey: .freqResolutionHz) ?? 0.0
        self.sourceResolutionHz = try c.decodeIfPresent(Double.self, forKey: .sourceResolutionHz) ?? 0.0
        self.fmaxHz = try c.decodeIfPresent(Double.self, forKey: .fmaxHz)
        self.envBandHz = try c.decodeIfPresent([Double].self, forKey: .envBandHz)
        self.waveform = try c.decodeIfPresent(Waveforms.self, forKey: .waveform)
        self.spectrum = try c.decode(Spectrum.self, forKey: .spectrum)
        self.thresholds = try c.decode([String: Staircase].self, forKey: .thresholds)
        self.bearingMarkers = try c.decode([FrequencyMarker].self, forKey: .bearingMarkers)
        self.order = try c.decodeIfPresent(OrderAnalysis.self, forKey: .order)
    }
}

public struct Waveforms: Codable, Sendable {
    public let accel: WaveformSeries
    public let velocity: WaveformSeries?
    public let envelope: WaveformSeries?
    enum CodingKeys: String, CodingKey {
        case accel, velocity, envelope
    }
}

/// A time waveform, min/max-downsampled. Plot ``values[i]`` at ``t_s[i]``: thinning keeps each bucket's min and
/// max, so the kept samples are unevenly spaced.
public struct WaveformSeries: Codable, Sendable {
    public let values: [Double]
    /// Each point's time, s, on the accel waveform's (and tach marks') base.
    public let tS: [Double]
    /// Start of this series: edge-trimmed waveforms start late.
    public let t0S: Double
    /// Mean spacing; exact (t0_s + i * dt_s) only when n_source == len(values).
    public let dtS: Double
    /// Samples before downsampling.
    public let nSource: Int
    enum CodingKeys: String, CodingKey {
        case values
        case tS = "t_s", t0S = "t0_s", dtS = "dt_s", nSource = "n_source"
    }
}

/// Peak-preserving decimated spectra on one shared frequency axis (Hz).
public struct Spectrum: Codable, Sendable {
    public let freqHz: [Double]
    public let accel: [Double]
    public let velocity: [Double]
    public let envelope: [Double]
    /// Spectrum lines before decimation.
    public let nSource: Int
    enum CodingKeys: String, CodingKey {
        case accel, velocity, envelope
        case freqHz = "freq_hz", nSource = "n_source"
    }
}

/// An envelope threshold staircase: x in Hz, y in the signal's unit.
public struct Staircase: Codable, Sendable {
    public let x: [Double]
    public let y: [Double]
    enum CodingKeys: String, CodingKey {
        case x, y
    }
}

public struct FrequencyMarker: Codable, Sendable {
    /// "shaft", "bpfo", "bpfi", "bsf" or "ftf".
    public let kind: String
    public let label: String
    public let hz: Double
    public let harmonic: Int
    enum CodingKeys: String, CodingKey {
        case kind, label, hz, harmonic
    }
}

/// Tach readings only: order analysis and the one-revolution view.
public struct OrderAnalysis: Codable, Sendable {
    public let shaftHz: Double
    public let rpm: Double
    /// Whole degrees, 0..359.
    public let phase1x: Int
    public let phase2x: Int
    public let amp1x: Double?
    public let amp2x: Double?
    public let phaseValid: Bool?
    public let phaseNote: String?
    /// 256 points over one revolution, velocity unit.
    public let oneRevVelocity: [Double]
    public let oneRevFit1x: [Double]
    /// One mark per revolution, seconds on the accel waveform's base.
    public let tachMarksS: [Double]
    /// Untrimmed accel sample count.
    public let nSamples: Int
    enum CodingKeys: String, CodingKey {
        case rpm
        case shaftHz = "shaft_hz", phase1x = "phase_1x", phase2x = "phase_2x", amp1x = "amp_1x", amp2x = "amp_2x"
        case phaseValid = "phase_valid", phaseNote = "phase_note", oneRevVelocity = "one_rev_velocity"
        case oneRevFit1x = "one_rev_fit_1x", tachMarksS = "tach_marks_s", nSamples = "n_samples"
    }
}

public struct Thermography: Codable, Sendable {
    public let thermograms: [Thermogram]
    public let hotspotCount: Int
    public let worstDeltaT: Double?
    enum CodingKeys: String, CodingKey {
        case thermograms
        case hotspotCount = "hotspot_count", worstDeltaT = "worst_delta_t"
    }
}

public struct Thermogram: Codable, Sendable {
    public let uuid: String
    public let url: String
    /// False until the thermogram has been analysed.
    public let processed: Bool
    public let meanTemp: Double?
    public let minTemp: Double?
    public let maxTemp: Double?
    public let hotClusters: [ThermogramHotCluster]
    enum CodingKeys: String, CodingKey {
        case uuid, url, processed
        case meanTemp = "mean_temp", minTemp = "min_temp", maxTemp = "max_temp", hotClusters = "hot_clusters"
    }
}

public struct ThermogramHotCluster: Codable, Sendable {
    public let cxPct: Double
    public let cyPct: Double
    public let maxTemp: Double?
    public let deltaT: Double?
    /// 3 minor, 4 major.
    public let severity: Int
    public let source: String?
    enum CodingKeys: String, CodingKey {
        case severity, source
        case cxPct = "cx_pct", cyPct = "cy_pct", maxTemp = "max_temp", deltaT = "delta_t"
    }
}

public struct ProcessResult: Codable, Sendable {
    public let type: String
    public let units: AnalysisUnits
    public let cursors: [ProcessCursor]
    enum CodingKeys: String, CodingKey {
        case type, units, cursors
    }
}

public struct ProcessCursor: Codable, Sendable {
    public let pointSequence: Int
    /// Hz, or ms for the waveform.
    public let x: [Double]
    public let y: [Double]
    public let peaks: [Peak]
    enum CodingKeys: String, CodingKey {
        case x, y, peaks
        case pointSequence = "point_sequence"
    }
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.pointSequence = try c.decode(Int.self, forKey: .pointSequence)
        self.x = try c.decode([Double].self, forKey: .x)
        self.y = try c.decode([Double].self, forKey: .y)
        self.peaks = try c.decodeIfPresent([Peak].self, forKey: .peaks) ?? []
    }
}

public struct Peak: Codable, Sendable {
    public let x: Double
    public let y: Double
    enum CodingKeys: String, CodingKey {
        case x, y
    }
}

public struct CompareResult: Codable, Sendable {
    public let pointId: Int
    public let spectrum: String
    public let units: AnalysisUnits
    public let zoomRangeHz: [Double]?
    public let baseline: Staircase?
    public let cursors: [CompareCursor]
    enum CodingKeys: String, CodingKey {
        case spectrum, units, baseline, cursors
        case pointId = "point_id", zoomRangeHz = "zoom_range_hz"
    }
}

public struct CompareCursor: Codable, Sendable {
    /// 1-based position in the requested seq list.
    public let index: Int
    public let pointSequence: Int
    public let color: String
    public let createdAt: String
    public let status: String
    public let fs: Double?
    public let metrics: JSONValue
    public let freqHz: [Double]
    public let values: [Double]
    public let markers: [FrequencyMarker]
    enum CodingKeys: String, CodingKey {
        case index, color, status, fs, metrics, values, markers
        case pointSequence = "point_sequence", createdAt = "created_at", freqHz = "freq_hz"
    }
}

public struct AssetTrend: Codable, Sendable {
    public let series: [TrendSeries]
    public let productionStatus: [ProductionSample]
    public let window: TimeWindow
    public let empty: Bool
    enum CodingKeys: String, CodingKey {
        case series, window, empty
        case productionStatus = "production_status"
    }
}

public struct TrendSeries: Codable, Sendable {
    public let pointId: Int
    public let name: String
    public let unit: String
    public let type: String
    public let location: String
    public let thresholds: TrendThresholds?
    public let measurements: [TrendReading]
    enum CodingKeys: String, CodingKey {
        case name, unit, type, location, thresholds, measurements
        case pointId = "point_id"
    }
}

public struct TrendReading: Codable, Sendable {
    public let t: String
    public let v: Double
    public let status: Int
    /// Taken while the asset was stopped.
    public let off: Bool
    enum CodingKeys: String, CodingKey {
        case t, v, status, off
    }
}

public struct TrendThresholds: Codable, Sendable {
    public let minor: Double?
    public let major: Double?
    public let direction: String
    enum CodingKeys: String, CodingKey {
        case minor, major, direction
    }
    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.minor = try c.decodeIfPresent(Double.self, forKey: .minor)
        self.major = try c.decodeIfPresent(Double.self, forKey: .major)
        self.direction = try c.decodeIfPresent(String.self, forKey: .direction) ?? "high"
    }
}

public struct ProductionSample: Codable, Sendable {
    public let t: String
    public let on: Bool
    enum CodingKeys: String, CodingKey {
        case t, on
    }
}

public struct TimeWindow: Codable, Sendable {
    public let start: String
    public let end: String
    enum CodingKeys: String, CodingKey {
        case start, end
    }
}

public struct FaultRecord: Codable, Sendable {
    public let assetId: Int
    public let at: String
    public let window: TimeWindow
    public let triggerPointId: Int?
    public let rows: [FaultRow]
    enum CodingKeys: String, CodingKey {
        case at, window, rows
        case assetId = "asset_id", triggerPointId = "trigger_point_id"
    }
}

public struct FaultRow: Codable, Sendable {
    public let pointId: Int
    public let name: String
    public let location: String
    public let transducerType: String
    public let status: Int
    public let unit: String
    public let series: [FaultSample]
    public let thresholds: TrendThresholds
    enum CodingKeys: String, CodingKey {
        case name, location, status, unit, series, thresholds
        case pointId = "point_id", transducerType = "transducer_type"
    }
}

public struct FaultSample: Codable, Sendable {
    public let t: String
    public let v: Double
    enum CodingKeys: String, CodingKey {
        case t, v
    }
}

public struct BaselineResult: Codable, Sendable {
    public let detail: String
    enum CodingKeys: String, CodingKey {
        case detail
    }
}

public struct BaselinePreview: Codable, Sendable {
    public let eligible: Int
    public let fitMin: Int
    enum CodingKeys: String, CodingKey {
        case eligible
        case fitMin = "fit_min"
    }
}
