"""Pure measurement primitives for mix verification.

Honest decode (sample count, not ffprobe estimate), onset-autocorrelation
BPM with confidence (never ``librosa.beat.beat_track``), beat grids, RMS
series, band energy, per-segment LUFS via ffmpeg ``ebur128``. No check
logic here - checks live in ``checks.py``.
"""

from __future__ import annotations

import itertools
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.audio.core.rhythm import find_beat_times, tempo_from_onset_autocorrelation

from .manifest import Manifest

ANALYSIS_SR = 22050
HOP_LENGTH = 512

# Vocal intelligibility band (fundamentals + formants).
VOCAL_BAND_HZ: tuple[float, float] = (200.0, 4000.0)
# Kick + bass fundamentals. Used to catch "empty" techno sections that are
# not silent enough to be dropouts.
LOW_BAND_HZ: tuple[float, float] = (25.0, 150.0)
# Low-mid mud zone — boxiness, unclear mixes.
MID_BAND_HZ: tuple[float, float] = (250.0, 500.0)
# High-frequency air band (clipped to nyquist at measurement time).
HIGH_BAND_HZ: tuple[float, float] = (5000.0, 20000.0)

_FFMPEG_TIMEOUT_S = 300.0


# ── audio IO ─────────────────────────────────────────────────────────


def load_audio(path: Path, sr: int = ANALYSIS_SR) -> tuple[np.ndarray, int]:
    """Decode a file to mono float32 at ``sr``. Honest: length = samples."""
    import librosa

    samples, out_sr = librosa.load(str(path), sr=sr, mono=True)
    return samples.astype(np.float32, copy=False), int(out_sr)


def load_audio_channels(path: Path, sr: int = ANALYSIS_SR) -> tuple[np.ndarray, int]:
    """Decode a file to channel-first float32 at ``sr``."""
    import librosa

    samples, out_sr = librosa.load(str(path), sr=sr, mono=False)
    channels = np.asarray(samples, dtype=np.float32)
    if channels.ndim == 1:
        channels = channels[np.newaxis, :]
    return channels, int(out_sr)


def ffprobe_duration(path: Path) -> float | None:
    """Container/bitrate-estimated duration as reported by ffprobe.

    This is the number that *lies* on streamed mp3s - we measure it only
    to compare against the honest decoded length.
    """
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=_FFMPEG_TIMEOUT_S,
            check=False,
        )
        raw = json.loads(proc.stdout or "{}").get("format", {}).get("duration")
        return float(raw) if raw is not None else None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


# ── rhythm ───────────────────────────────────────────────────────────


def _onset_envelope(samples: np.ndarray, sr: int) -> np.ndarray:
    import librosa

    env = librosa.onset.onset_strength(y=samples, sr=sr, hop_length=HOP_LENGTH)
    return np.asarray(env, dtype=np.float64)


def estimate_bpm(
    samples: np.ndarray,
    sr: int,
    *,
    min_bpm: float = 100.0,
    max_bpm: float = 200.0,
) -> tuple[float, float]:
    """Onset-autocorrelation BPM with parabolic sub-frame precision.

    Returns ``(bpm, confidence)``; ``(0.0, 0.0)`` on degenerate input.
    Never uses ``librosa.beat.beat_track`` - it quantizes tempo to a
    fixed integer-frames-per-beat grid.
    """
    env = _onset_envelope(samples, sr)
    est = tempo_from_onset_autocorrelation(env, sr, HOP_LENGTH, min_bpm=min_bpm, max_bpm=max_bpm)
    return est.bpm, est.confidence


def beat_grid(samples: np.ndarray, sr: int, bpm_hint: float | None = None) -> np.ndarray:
    """Beat positions in seconds, guided by ``bpm_hint`` when known."""
    env = _onset_envelope(samples, sr)
    return np.asarray(find_beat_times(env, sr, HOP_LENGTH, bpm_hint=bpm_hint))


# ── level / spectrum ─────────────────────────────────────────────────


def rms_series(
    samples: np.ndarray,
    sr: int,
    *,
    window_s: float = 0.4,
    hop_s: float = 0.2,
) -> tuple[np.ndarray, np.ndarray]:
    """Windowed RMS in dBFS. Returns ``(window_center_times_s, rms_db)``."""
    win = max(1, int(window_s * sr))
    hop = max(1, int(hop_s * sr))
    if len(samples) < win:
        rms = (
            float(np.sqrt(np.mean(np.square(samples), dtype=np.float64))) if len(samples) else 0.0
        )
        return np.array([len(samples) / (2 * sr)]), np.array([_to_db(rms)])

    starts = np.arange(0, len(samples) - win + 1, hop)
    times = (starts + win / 2) / sr
    rms_db = np.empty(len(starts), dtype=np.float64)
    for i, s in enumerate(starts):
        chunk = samples[s : s + win].astype(np.float64)
        rms_db[i] = _to_db(float(np.sqrt(np.mean(np.square(chunk)))))
    return times, rms_db


def band_rms_series(
    samples: np.ndarray,
    sr: int,
    band_hz: tuple[float, float],
    *,
    window_s: float = 2.0,
    hop_s: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Windowed RMS after a Butterworth band filter."""
    filtered = _filter_band(samples, sr, band_hz)
    return rms_series(filtered, sr, window_s=window_s, hop_s=hop_s)


def band_rms_db(
    samples: np.ndarray,
    sr: int,
    band_hz: tuple[float, float] = VOCAL_BAND_HZ,
) -> float:
    """RMS (dBFS) of the signal restricted to ``band_hz`` via rFFT mask."""
    if len(samples) == 0:
        return _to_db(0.0)
    spectrum = np.fft.rfft(samples.astype(np.float64))
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / sr)
    mask = (freqs >= band_hz[0]) & (freqs <= band_hz[1])
    spectrum[~mask] = 0.0
    filtered = np.fft.irfft(spectrum, n=len(samples))
    return _to_db(float(np.sqrt(np.mean(np.square(filtered)))))


def stereo_summary(channels: np.ndarray) -> tuple[tuple[float, float] | None, float | None]:
    """Return ``((left_db, right_db), correlation)`` for stereo material."""
    if channels.ndim != 2 or channels.shape[0] < 2 or channels.shape[1] == 0:
        return None, None
    left = channels[0].astype(np.float64)
    right = channels[1].astype(np.float64)
    left_db = _to_db(float(np.sqrt(np.mean(np.square(left)))))
    right_db = _to_db(float(np.sqrt(np.mean(np.square(right)))))
    if float(np.std(left)) < 1e-9 or float(np.std(right)) < 1e-9:
        corr = None
    else:
        corr = float(np.corrcoef(left, right)[0, 1])
    return (left_db, right_db), corr


def _filter_band(samples: np.ndarray, sr: int, band_hz: tuple[float, float]) -> np.ndarray:
    from scipy.signal import butter, sosfiltfilt

    if len(samples) < 64:
        return samples.astype(np.float32, copy=False)
    low, high = band_hz
    nyquist = sr / 2.0
    if low <= 0 and high >= nyquist:
        return samples.astype(np.float32, copy=False)
    if low <= 0:
        sos = butter(4, high, btype="lowpass", fs=sr, output="sos")
    elif high >= nyquist:
        sos = butter(4, low, btype="highpass", fs=sr, output="sos")
    else:
        sos = butter(4, (low, high), btype="bandpass", fs=sr, output="sos")
    return np.asarray(sosfiltfilt(sos, samples), dtype=np.float32)


def _to_db(linear: float) -> float:
    return 20.0 * float(np.log10(max(linear, 1e-10)))


# ── ffmpeg-side measurements ─────────────────────────────────────────

_EBUR128_I_RE = re.compile(r"I:\s*(-?[\d.]+)\s*LUFS")
_MAX_VOLUME_RE = re.compile(r"max_volume:\s*(-?[\d.]+)\s*dB")


def segment_lufs(path: Path, start_s: float, duration_s: float) -> float | None:
    """Integrated LUFS of ``[start_s, start_s + duration_s]`` via ebur128."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-ss",
                f"{start_s:.3f}",
                "-t",
                f"{duration_s:.3f}",
                "-i",
                str(path),
                "-filter_complex",
                "ebur128",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=_FFMPEG_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    matches = _EBUR128_I_RE.findall(proc.stderr)
    return float(matches[-1]) if matches else None


def max_volume_db(path: Path) -> float | None:
    """Peak level in dBFS via ffmpeg volumedetect."""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-i",
                str(path),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=_FFMPEG_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = _MAX_VOLUME_RE.search(proc.stderr)
    return float(match.group(1)) if match else None


# ── aggregated measurements ──────────────────────────────────────────


@dataclass(slots=True)
class SourceMeasure:
    """Measurements for one source file (backbone or a layer source)."""

    path: Path
    exists: bool = False
    decoded_duration: float | None = None
    ffprobe_dur: float | None = None
    bpm: float | None = None
    bpm_confidence: float | None = None
    beat_times: np.ndarray | None = None


@dataclass(slots=True)
class LayerMasking:
    """Vocal-band levels for one vocal layer window (post-gain, dBFS)."""

    layer_index: int
    vocal_band_db: float
    bed_band_db: float


@dataclass(slots=True)
class OutputMeasure:
    """Measurements of the rendered output file."""

    path: Path
    exists: bool = False
    decoded_duration: float | None = None
    rms_times: np.ndarray | None = None
    rms_db: np.ndarray | None = None
    low_rms_times: np.ndarray | None = None
    low_rms_db: np.ndarray | None = None
    max_volume: float | None = None
    sample_peak_db: float | None = None
    clipped_sample_count: int = 0
    channel_rms_db: tuple[float, float] | None = None
    stereo_correlation: float | None = None
    bpm: float | None = None
    bpm_confidence: float | None = None
    crest_factor: float | None = None
    low_band_pct: float | None = None
    mid_band_pct: float | None = None
    high_band_pct: float | None = None
    low_end_corr: float | None = None
    # Windowed analysis (standalone)
    energy_range_db: float | None = None
    rms_min_time: float | None = None  # when the quietest moment occurs
    rms_max_time: float | None = None  # when the loudest moment occurs
    energy_dip_count: int = 0
    energy_dip_times: list[tuple[float, float]] = field(default_factory=list)
    bpm_stability: float | None = None
    bpm_windows: list[tuple[float, float, float]] = field(default_factory=list)
    rms_jumps_per_min: float | None = None
    first_clip_time: float | None = None  # first clipped sample position
    rms_jump_times: list[tuple[float, float]] = field(default_factory=list)
    # [(start_s, end_s, integrated_lufs_or_None), ...]
    segments: list[tuple[float, float, float | None]] = field(default_factory=list)
    # Kick drop-out events (low-band dip while mix plays)
    kick_drop_count: int = 0
    kick_drop_events: list[tuple[float, float]] = field(default_factory=list)
    # Energy trend slope (dB per minute of mix time)
    energy_slope_db_per_min: float | None = None


@dataclass(slots=True)
class Measurements:
    """Everything the checks need, precomputed once."""

    backbone: SourceMeasure
    layers: dict[int, SourceMeasure] = field(default_factory=dict)
    masking: list[LayerMasking] = field(default_factory=list)
    output: OutputMeasure | None = None


def segment_boundaries(manifest: Manifest, total_duration: float) -> list[float]:
    """Timeline cut points: 0, every layer start/end, total duration."""
    points = {0.0, total_duration}
    for layer in manifest.layers:
        for t in (layer.place_at, layer.out_end):
            if 0.0 < t < total_duration:
                points.add(round(t, 3))
    return sorted(points)


def _measure_source(
    path: Path,
    *,
    bpm_hint: float | None,
    min_bpm: float,
    max_bpm: float,
) -> tuple[SourceMeasure, np.ndarray | None]:
    """Measure one source; returns the measure + decoded samples (or None)."""
    measure = SourceMeasure(path=path)
    if not path.is_file():
        return measure, None
    measure.exists = True
    measure.ffprobe_dur = ffprobe_duration(path)
    samples, sr = load_audio(path)
    measure.decoded_duration = len(samples) / sr
    measure.bpm, measure.bpm_confidence = estimate_bpm(
        samples, sr, min_bpm=min_bpm, max_bpm=max_bpm
    )
    measure.beat_times = beat_grid(samples, sr, bpm_hint=bpm_hint or measure.bpm)
    return measure, samples


def collect_measurements(
    manifest: Manifest,
    *,
    min_bpm: float = 100.0,
    max_bpm: float = 200.0,
    min_segment_s: float = 3.0,
    skip_output: bool = False,
) -> Measurements:
    """Run every measurement the checks need. Missing files degrade to
    ``exists=False`` - the corresponding checks WARN instead of crashing."""
    backbone_measure, backbone_samples = _measure_source(
        manifest.backbone_path,
        bpm_hint=manifest.backbone.bpm,
        min_bpm=min_bpm,
        max_bpm=max_bpm,
    )
    measurements = Measurements(backbone=backbone_measure)

    layer_samples: dict[int, np.ndarray] = {}
    for i, layer in enumerate(manifest.layers):
        measure, samples = _measure_source(
            manifest.layer_path(layer),
            bpm_hint=manifest.backbone.bpm,
            min_bpm=min_bpm,
            max_bpm=max_bpm,
        )
        measurements.layers[i] = measure
        if samples is not None:
            layer_samples[i] = samples

    # Vocal-masking band levels: isolated vocal (trimmed, gained) vs the
    # backbone bed in the same output window. Backbone maps 1:1 to the
    # output timeline (it is never stretched).
    if backbone_samples is not None:
        for i, layer in enumerate(manifest.layers):
            if layer.role != "vocal" or i not in layer_samples:
                continue
            sr = ANALYSIS_SR
            vocal = layer_samples[i][int(layer.src_trim[0] * sr) : int(layer.src_trim[1] * sr)]
            bed = backbone_samples[int(layer.place_at * sr) : int(layer.out_end * sr)]
            if len(vocal) == 0 or len(bed) == 0:
                continue
            vocal_db = band_rms_db(vocal, sr) + _gain_db(layer.gain)
            bed_db = band_rms_db(bed, sr) + _gain_db(manifest.backbone.gain)
            measurements.masking.append(
                LayerMasking(layer_index=i, vocal_band_db=vocal_db, bed_band_db=bed_db)
            )

    if skip_output:
        return measurements

    out_path = manifest.output_path
    output = OutputMeasure(path=out_path)
    measurements.output = output
    if not out_path.is_file():
        return measurements

    output.exists = True
    out_channels, out_sr = load_audio_channels(out_path)
    out_samples = np.mean(out_channels, axis=0)
    output.decoded_duration = len(out_samples) / out_sr
    output.rms_times, output.rms_db = rms_series(out_samples, out_sr)
    output.low_rms_times, output.low_rms_db = band_rms_series(out_samples, out_sr, LOW_BAND_HZ)
    output.max_volume = max_volume_db(out_path)
    peak = float(np.max(np.abs(out_channels))) if out_channels.size else 0.0
    output.sample_peak_db = _to_db(peak)
    output.clipped_sample_count = int(np.count_nonzero(np.abs(out_channels) >= 0.999))
    output.channel_rms_db, output.stereo_correlation = stereo_summary(out_channels)

    bounds = segment_boundaries(manifest, output.decoded_duration)
    for start, end in itertools.pairwise(bounds):
        if end - start < min_segment_s:
            continue
        output.segments.append((start, end, segment_lufs(out_path, start, end - start)))

    return measurements


def collect_single_file_measurements(
    path: Path,
    *,
    min_bpm: float = 100.0,
    max_bpm: float = 200.0,
    min_segment_s: float = 3.0,
) -> OutputMeasure:
    """Measure a single audio file without a manifest (standalone mode).

    Returns an :class:`OutputMeasure` with all available metrics.
    Missing files degrade to ``exists=False``.
    """
    output = OutputMeasure(path=path)
    if not path.is_file():
        return output

    output.exists = True
    out_channels, out_sr = load_audio_channels(path)
    out_samples = np.mean(out_channels, axis=0)
    output.decoded_duration = len(out_samples) / out_sr
    output.rms_times, output.rms_db = rms_series(out_samples, out_sr)
    output.low_rms_times, output.low_rms_db = band_rms_series(out_samples, out_sr, LOW_BAND_HZ)
    output.max_volume = max_volume_db(path)
    peak = float(np.max(np.abs(out_channels))) if out_channels.size else 0.0
    output.sample_peak_db = _to_db(peak)
    output.clipped_sample_count = int(np.count_nonzero(np.abs(out_channels) >= 0.999))
    if output.clipped_sample_count > 0:
        clip_mask = np.any(np.abs(out_channels) >= 0.999, axis=0)
        first_clip_idx = int(np.argmax(clip_mask))
        output.first_clip_time = first_clip_idx / out_sr
    output.channel_rms_db, output.stereo_correlation = stereo_summary(out_channels)
    output.segments = [(0.0, output.decoded_duration, segment_lufs(path, 0.0, output.decoded_duration))]
    output.bpm, output.bpm_confidence = estimate_bpm(out_samples, out_sr, min_bpm=min_bpm, max_bpm=max_bpm)

    # Crest factor: peak-to-average-RMS ratio
    if output.sample_peak_db is not None and len(output.rms_db) > 0:
        output.crest_factor = output.sample_peak_db - float(np.mean(output.rms_db))

    # Spectral energy distribution
    full_rms_lin = float(np.sqrt(np.mean(np.square(out_samples))))
    if full_rms_lin > 1e-10:
        low_f = _filter_band(out_samples, out_sr, LOW_BAND_HZ)
        output.low_band_pct = (float(np.sqrt(np.mean(np.square(low_f)))) / full_rms_lin) ** 2 * 100

        mid_f = _filter_band(out_samples, out_sr, MID_BAND_HZ)
        output.mid_band_pct = (float(np.sqrt(np.mean(np.square(mid_f)))) / full_rms_lin) ** 2 * 100

        high_nyq = min(HIGH_BAND_HZ[1], out_sr / 2 - 1)
        if high_nyq > HIGH_BAND_HZ[0]:
            high_f = _filter_band(out_samples, out_sr, (HIGH_BAND_HZ[0], high_nyq))
            output.high_band_pct = (float(np.sqrt(np.mean(np.square(high_f)))) / full_rms_lin) ** 2 * 100

    # Low-end stereo correlation (phase coherence < 150 Hz)
    if out_channels.shape[0] >= 2:
        left_low = _filter_band(out_channels[0], out_sr, LOW_BAND_HZ)
        right_low = _filter_band(out_channels[1], out_sr, LOW_BAND_HZ)
        if len(left_low) > 1 and len(right_low) > 1:
            corr = float(np.corrcoef(left_low, right_low)[0, 1])
            if not np.isnan(corr):
                output.low_end_corr = corr

    # ── windowed analysis ──────────────────────────────────────────

    # Energy range: max RMS - min RMS (dB) + locate quietest/loudest
    if output.rms_db is not None and len(output.rms_db) > 0:
        rms = output.rms_db
        times = output.rms_times
        output.energy_range_db = float(np.max(rms) - np.min(rms))
        output.rms_min_time = float(times[np.argmin(rms)]) if times is not None else None
        output.rms_max_time = float(times[np.argmax(rms)]) if times is not None else None

    # Energy dips: sustained windows (≥5 s) where short-term RMS drops
    # below 30 % of the global mean. Records every dip's (start_s, end_s).
    if output.rms_db is not None and len(output.rms_db) > 2:
        hop_s = float(output.rms_times[1] - output.rms_times[0]) if len(output.rms_times) >= 2 else 0.2
        window_len = max(1, int(3.0 / hop_s))
        mean_linear = float(np.mean(10.0 ** (output.rms_db / 20.0)))
        dip_threshold = mean_linear * 0.3
        short_rms = np.convolve(
            10.0 ** (output.rms_db / 20.0),
            np.ones(window_len) / window_len,
            mode="valid",
        )
        below = short_rms < dip_threshold
        min_dip_frames = max(1, int(5.0 / hop_s))
        gaps = np.diff(np.concatenate(([False], below, [False]))).astype(int)
        onsets = np.where(gaps == 1)[0]
        offsets = np.where(gaps == -1)[0]
        n = min(len(onsets), len(offsets))
        sustained = 0
        dip_times: list[tuple[float, float]] = []
        for i in range(n):
            if (offsets[i] - onsets[i]) >= min_dip_frames:
                sustained += 1
                t_start = float(output.rms_times[onsets[i] * hop_s // hop_s if onsets[i] < len(output.rms_times) else 0])
                t_end = float(output.rms_times[min(offsets[i], len(output.rms_times) - 1)])
                dip_times.append((t_start, t_end))
        output.energy_dip_count = int(sustained)
        output.energy_dip_times = dip_times

    # BPM stability: std of BPM across 30-second windows + per-window log.
    total_s = len(out_samples) / out_sr
    window_s = 30.0
    hop_w = int(window_s * out_sr)
    bpms: list[float] = []
    bpm_win: list[tuple[float, float, float]] = []
    for start in range(0, len(out_samples) - hop_w + 1, hop_w):
        chunk = out_samples[start : start + hop_w]
        bpm, conf = estimate_bpm(chunk, out_sr, min_bpm=min_bpm, max_bpm=max_bpm)
        t = start / out_sr
        bpm_win.append((t, bpm, conf))
        if bpm > 0 and conf > 0.1:
            bpms.append(bpm)
    output.bpm_windows = bpm_win
    if len(bpms) >= 3:
        output.bpm_stability = float(np.std(bpms))

    # Kick consistency: low-band energy drop while full mix plays.
    # In techno the kick is the foundation — sections where it disappears
    # (but the mix isn't silent) are likely problematic breakdowns or
    # transition errors.
    if output.low_rms_db is not None and output.low_rms_times is not None and output.rms_db is not None:
        low_t = output.low_rms_times
        if len(low_t) >= 3 and len(output.low_rms_db) >= 3:
            low_median = float(np.median(output.low_rms_db))
            kick_floor = low_median - 8.0
            full_at_low = np.interp(low_t, output.rms_times, output.rms_db)
            mix_playing = full_at_low > -30.0
            kick_gone = (output.low_rms_db < kick_floor) & mix_playing
            runs = _true_runs(kick_gone)
            hop_s = float(low_t[1] - low_t[0]) if len(low_t) >= 2 else 1.0
            min_event_s = 4.0
            events = [
                (float(low_t[a]), float(low_t[b - 1]))
                for a, b in runs
                if (b - a) * hop_s >= min_event_s
            ]
            output.kick_drop_events = events
            output.kick_drop_count = len(events)

    # Energy slope: linear trend of smoothed RMS over the full mix.
    # Negative = energy declining (mix loses steam), positive = building.
    if output.rms_db is not None and len(output.rms_db) > 20:
        hop_s = float(output.rms_times[1] - output.rms_times[0]) if len(output.rms_times) >= 2 else 0.2
        win = max(1, int(10.0 / hop_s))
        smooth = np.convolve(output.rms_db, np.ones(win) / win, mode="valid")
        t = np.arange(len(smooth), dtype=np.float64) * hop_s / 60.0  # minutes
        if len(t) >= 3:
            coeffs = np.polyfit(t, smooth, deg=1)
            output.energy_slope_db_per_min = float(coeffs[0])

    # RMS jumps: abrupt level changes (>9 dB) between adjacent 3-second
    # smoothed RMS windows. Records every jump's time and magnitude.
    if output.rms_db is not None and len(output.rms_db) > 10:
        hop_s = float(output.rms_times[1] - output.rms_times[0]) if len(output.rms_times) >= 2 else 0.2
        win = max(1, int(3.0 / hop_s))
        smooth = np.convolve(output.rms_db, np.ones(win) / win, mode="valid")
        diffs = np.diff(smooth)
        jump_mask = np.abs(diffs) > 9.0
        jumps = int(np.sum(jump_mask))
        output.rms_jumps_per_min = jumps / (total_s / 60.0) if total_s > 0 else 0.0
        jump_indices = np.where(jump_mask)[0]
        pad = win // 2
        output.rms_jump_times = [
            (float(output.rms_times[min(idx + pad, len(output.rms_times) - 1)]), float(diffs[idx]))
            for idx in jump_indices[:20]  # cap at 20 to keep output sane
        ]

    return output


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous True runs in a boolean array as [start, end) pairs."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def _gain_db(gain: float) -> float:
    return 20.0 * float(np.log10(max(gain, 1e-10)))
