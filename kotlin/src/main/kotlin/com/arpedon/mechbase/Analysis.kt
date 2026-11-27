package com.arpedon.mechbase

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** What the web reading page draws. Arrays are in [units]; frequencies are Hz (display = hz × [AnalysisUnits.frequencyScale]). */
@Serializable
data class ReadingAnalysis(
    val uuid: String,
    @SerialName("point_id") val pointId: Int,
    @SerialName("point_sequence") val pointSequence: Int,
    @SerialName("created_at") val createdAt: String = "",
    val status: String = "",
    val notes: String = "",
    @SerialName("transducer_type") val transducerType: String = "",
    val source: String? = null,
    @SerialName("previous_sequence") val previousSequence: Int? = null,
    @SerialName("next_sequence") val nextSequence: Int? = null,
    val data: JsonObject = JsonObject(emptyMap()),
    @SerialName("display_units") val displayUnits: Map<String, DisplayUnit> = emptyMap(),
    val units: AnalysisUnits,
    val filter: AnalysisFilter? = null,
    val vibration: VibrationAnalysis? = null,
    val thermography: Thermography? = null,
    val attachments: List<FileAttachment> = emptyList(),
)

/** The viewer's units; [frequencyScale] is 60 for CPM. */
@Serializable
data class AnalysisUnits(
    val acceleration: String = "",
    val velocity: String = "",
    val temperature: String = "",
    val frequency: String = "",
    @SerialName("frequency_scale") val frequencyScale: Double,
)

@Serializable
data class AnalysisFilter(
    @SerialName("highpass_hz") val highpassHz: Double? = null,
    @SerialName("lowpass_hz") val lowpassHz: Double? = null,
)

/** Spectra are ≤3200 lines; [nLines] and [freqResolutionHz] describe what is returned. */
@Serializable
data class VibrationAnalysis(
    val fs: Double? = null,
    @SerialName("n_lines") val nLines: Int = 0,
    @SerialName("freq_resolution_hz") val freqResolutionHz: Double = 0.0,
    /** The FFT bin width before thinning: pass it as `df` to [Findings.create]. */
    @SerialName("source_resolution_hz") val sourceResolutionHz: Double = 0.0,
    @SerialName("fmax_hz") val fmaxHz: Double? = null,
    @SerialName("env_band_hz") val envBandHz: List<Double>? = null,
    val waveform: Waveforms? = null,
    val spectrum: Spectrum,
    /** Keyed by "accel" / "velocity" / "envelope". */
    val thresholds: Map<String, Staircase> = emptyMap(),
    @SerialName("bearing_markers") val bearingMarkers: List<FrequencyMarker> = emptyList(),
    val order: OrderAnalysis? = null,
)

@Serializable
data class Waveforms(
    val accel: WaveformSeries,
    val velocity: WaveformSeries? = null,
    val envelope: WaveformSeries? = null,
)

@Serializable
data class WaveformSeries(
    val values: List<Double> = emptyList(),
    /** True sample times, s (after min/max thinning): use these for x. */
    @SerialName("t_s") val t: List<Double> = emptyList(),
    @SerialName("t0_s") val t0: Double,
    /** `t0 + i*dt` is exact only when [nSource] equals `values.size`. */
    @SerialName("dt_s") val dt: Double,
    @SerialName("n_source") val nSource: Int,
)

@Serializable
data class Spectrum(
    @SerialName("freq_hz") val freqHz: List<Double> = emptyList(),
    val accel: List<Double> = emptyList(),
    val velocity: List<Double> = emptyList(),
    val envelope: List<Double> = emptyList(),
    @SerialName("n_source") val nSource: Int,
)

/** A stepped threshold line. */
@Serializable
data class Staircase(
    val x: List<Double> = emptyList(),
    val y: List<Double> = emptyList(),
)

@Serializable
data class FrequencyMarker(
    val kind: String = "",
    val label: String = "",
    val hz: Double,
    val harmonic: Int,
)

@Serializable
data class OrderAnalysis(
    @SerialName("shaft_hz") val shaftHz: Double,
    val rpm: Double,
    @SerialName("phase_1x") val phase1x: Int,
    @SerialName("phase_2x") val phase2x: Int,
    @SerialName("amp_1x") val amp1x: Double? = null,
    @SerialName("amp_2x") val amp2x: Double? = null,
    @SerialName("phase_valid") val phaseValid: Boolean? = null,
    @SerialName("phase_note") val phaseNote: String? = null,
    @SerialName("one_rev_velocity") val oneRevVelocity: List<Double> = emptyList(),
    @SerialName("one_rev_fit_1x") val oneRevFit1x: List<Double> = emptyList(),
    @SerialName("tach_marks_s") val tachMarks: List<Double> = emptyList(),
    @SerialName("n_samples") val nSamples: Int,
)

@Serializable
data class Thermography(
    val thermograms: List<Thermogram> = emptyList(),
    @SerialName("hotspot_count") val hotspotCount: Int,
    @SerialName("worst_delta_t") val worstDeltaT: Double? = null,
)

/** [url] is signed and expires: never cache it, refetch the analysis. */
@Serializable
data class Thermogram(
    val uuid: String,
    val url: String = "",
    val processed: Boolean,
    @SerialName("mean_temp") val meanTemp: Double? = null,
    @SerialName("min_temp") val minTemp: Double? = null,
    @SerialName("max_temp") val maxTemp: Double? = null,
    @SerialName("hot_clusters") val hotClusters: List<ThermogramHotspot> = emptyList(),
)

/** A thermogram hotspot; [severity] 3 minor, 4 major. */
@Serializable
data class ThermogramHotspot(
    @SerialName("cx_pct") val cxPct: Double,
    @SerialName("cy_pct") val cyPct: Double,
    @SerialName("max_temp") val maxTemp: Double? = null,
    @SerialName("delta_t") val deltaT: Double? = null,
    val severity: Int,
    val source: String? = null,
)

/** Processed cursors: x in ms for `waveform`, else Hz; y in [units]. A missing or foreign cursor has empty arrays. */
@Serializable
data class ProcessResult(
    val type: String = "",
    val units: AnalysisUnits,
    val cursors: List<ProcessCursor> = emptyList(),
)

@Serializable
data class ProcessCursor(
    @SerialName("point_sequence") val pointSequence: Int,
    val x: List<Double> = emptyList(),
    val y: List<Double> = emptyList(),
    val peaks: List<Peak> = emptyList(),
)

@Serializable
data class Peak(
    val x: Double,
    val y: Double,
)

/** Overlay spectra of up to 8 readings of one point; [baseline] is the first reading's envelope threshold. */
@Serializable
data class PointComparison(
    @SerialName("point_id") val pointId: Int,
    val spectrum: String = "",
    val units: AnalysisUnits,
    @SerialName("zoom_range_hz") val zoomRangeHz: List<Double>? = null,
    val baseline: Staircase? = null,
    val cursors: List<CompareCursor> = emptyList(),
)

@Serializable
data class CompareCursor(
    val index: Int,
    @SerialName("point_sequence") val pointSequence: Int,
    val color: String = "",
    @SerialName("created_at") val createdAt: String = "",
    val status: String = "",
    val fs: Double? = null,
    val metrics: JsonObject = JsonObject(emptyMap()),
    @SerialName("freq_hz") val freqHz: List<Double> = emptyList(),
    val values: List<Double> = emptyList(),
    val markers: List<FrequencyMarker> = emptyList(),
)

/** The asset chart: one series per non-Production point in the viewer's units, Production on/off samples, and the window. */
@Serializable
data class AssetTrend(
    val series: List<TrendSeries> = emptyList(),
    @SerialName("production_status") val productionStatus: List<ProductionSample> = emptyList(),
    val window: TimeWindow,
    val empty: Boolean,
)

@Serializable
data class TrendSeries(
    @SerialName("point_id") val pointId: Int,
    val name: String = "",
    val unit: String = "",
    val type: String = "",
    val location: String = "",
    val thresholds: TrendThresholds? = null,
    val measurements: List<TrendReading> = emptyList(),
)

@Serializable
data class TrendReading(
    val t: String = "",
    val v: Double,
    val status: Int,
    val off: Boolean,
)

@Serializable
data class TrendThresholds(
    val minor: Double? = null,
    val major: Double? = null,
    val direction: String = "high",
)

@Serializable
data class ProductionSample(
    val t: String = "",
    val on: Boolean,
)

@Serializable
data class TimeWindow(
    val start: String = "",
    val end: String = "",
)

/** Every scalar point's readings within 60 s of [at], native units, with limits. */
@Serializable
data class FaultRecord(
    @SerialName("asset_id") val assetId: Int,
    val at: String = "",
    val window: TimeWindow,
    @SerialName("trigger_point_id") val triggerPointId: Int? = null,
    val rows: List<FaultRow> = emptyList(),
)

@Serializable
data class FaultRow(
    @SerialName("point_id") val pointId: Int,
    val name: String = "",
    val location: String = "",
    @SerialName("transducer_type") val transducerType: String = "",
    val status: Int,
    val unit: String = "",
    val series: List<FaultSample> = emptyList(),
    val thresholds: TrendThresholds,
)

@Serializable
data class FaultSample(
    val t: String = "",
    val v: Double,
)

/** [eligible] usable readings since the date; a fit needs [fitMin]. */
@Serializable
data class BaselinePreview(
    val eligible: Int,
    @SerialName("fit_min") val fitMin: Int,
)

@Serializable
private data class ProcessBody(
    val type: String,
    @SerialName("high_pass") val highPass: Double,
    @SerialName("low_pass") val lowPass: Double,
    @SerialName("db_scale") val dbScale: Boolean,
    @SerialName("peak_count") val peakCount: Int,
    val cursors: List<Int>,
)

@Serializable
private data class BaselineOut(val detail: String = "")

/** Reading analysis, compare, asset trend, fault record and baselines. */
class Analysis internal constructor(private val http: Http, private val installationId: Int) {
    private fun point(pointId: Int, suffix: String) = installationPath(installationId, "/measurement-points/$pointId$suffix")

    /** [highpassHz] / [lowpassHz] reprocess the waveform (each in (0, fs/2), high below low, else 422). */
    suspend fun reading(
        pointId: Int,
        pointSequence: Int,
        highpassHz: Double? = null,
        lowpassHz: Double? = null,
    ): ReadingAnalysis = http.getJson(
        point(pointId, "/measurements/$pointSequence/analysis"),
        mapOf("highpass_hz" to highpassHz, "lowpass_hz" to lowpassHz),
        ReadingAnalysis.serializer(),
    )

    /**
     * The compare panel's processing over up to 8 readings of this point ([cursors], by point_sequence;
     * empty = this reading). [type] is accel | velocity | envelope | waveform; 0 Hz means no filter.
     */
    suspend fun process(
        pointId: Int,
        pointSequence: Int,
        type: String = "velocity",
        highPass: Double = 0.0,
        lowPass: Double = 0.0,
        dbScale: Boolean = false,
        peakCount: Int = 0,
        cursors: List<Int> = emptyList(),
    ): ProcessResult = http.postJson(
        point(pointId, "/measurements/$pointSequence/process"),
        SDK_JSON.encodeToJsonElement(
            ProcessBody.serializer(),
            ProcessBody(type, highPass, lowPass, dbScale, peakCount, cursors),
        ),
        ProcessResult.serializer(),
    )

    /** Overlay spectra of [sequences] (≤8, else 422; unknown ones skipped). [spectrum] is accel | velocity | envelope. Conditional: see [Conditional]. */
    suspend fun compare(
        pointId: Int,
        sequences: List<Int>,
        spectrum: String = "velocity",
        ifNoneMatch: String? = null,
    ): Conditional<PointComparison> {
        require(sequences.isNotEmpty()) { "compare needs at least one point_sequence" }
        return http.getConditional(
            point(pointId, "/compare"),
            mapOf("seq" to sequences.joinToString(","), "spectrum" to spectrum),
            PointComparison.serializer(),
            ifNoneMatch,
        )
    }

    /** The asset chart over 7 days back from its latest reading; [type] narrows to one transducer type. */
    suspend fun trend(assetId: Int, type: String? = null): AssetTrend =
        http.getJson(installationPath(installationId, "/assets/$assetId/trend"), mapOf("type" to type), AssetTrend.serializer())

    /** Readings within 60 s of [at] (ISO 8601). [pointId] names the point whose reading raised the change. */
    suspend fun faultRecord(assetId: Int, at: String, pointId: Int? = null): FaultRecord =
        http.getJson(
            installationPath(installationId, "/assets/$assetId/fault-record"),
            mapOf("at" to at, "point" to pointId),
            FaultRecord.serializer(),
        )

    /** Queue a baseline fit over readings on and after [refitFrom] (ISO date). 422 under the preview's `fitMin`. Returns the server's message. */
    suspend fun createBaseline(pointId: Int, refitFrom: String): String =
        http.postJson(point(pointId, "/baseline"), buildJsonObject { put("refit_from", refitFrom) }, BaselineOut.serializer()).detail

    /** Remove the point's operating modes and spectral baselines (back to ISO limits). Returns the server's message. */
    suspend fun clearBaseline(pointId: Int): String =
        http.sendJson("DELETE", point(pointId, "/baseline"), null, null, BaselineOut.serializer()).detail

    /** Usable readings on or after [since] (YYYY-MM-DD). */
    suspend fun baselinePreview(pointId: Int, since: String? = null): BaselinePreview =
        http.getJson(point(pointId, "/baseline/preview"), mapOf("since" to since), BaselinePreview.serializer())
}
