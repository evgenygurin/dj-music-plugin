"""Measurement primitives for DJ mix verification."""

from __future__ import annotations

import itertools
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.audio.render._constants import SR as _SR
from app.audio.render.verify.manifest import DJManifest, DJSource

__all__ = [
    "DJManifest",
    "DJSource",
    "OutputMeasure",
    "SourceMeasure",
    "build_verify_manifest",
    "measure_output",
    "measure_source",
    "segment_boundaries",
]

_ANALYSIS_SR: int = _SR
_HOP_LENGTH: int = 512
_FFMPEG_TIMEOUT_S: float = 300.0


def load_audio(path: str, sr: int = _ANALYSIS_SR) -> tuple[np.ndarray, int]:
    import librosa

    samples, out_sr = librosa.load(path, sr=sr, mono=True)
    return samples.astype(np.float32, copy=False), int(out_sr)


def load_audio_stereo(path: str, sr: int = _ANALYSIS_SR) -> tuple[np.ndarray, int]:
    import librosa

    channels, out_sr = librosa.load(path, sr=sr, mono=False)
    if channels.ndim == 1:
        channels = channels[np.newaxis, :]
    return channels.astype(np.float32, copy=False), int(out_sr)


def estimate_bpm(
    samples: np.ndarray, sr: int, *, min_bpm: float = 100.0, max_bpm: float = 200.0
) -> tuple[float, float]:
    import librosa

    from app.audio.core.rhythm import tempo_from_onset_autocorrelation as _tempo

    env = librosa.onset.onset_strength(y=samples, sr=sr, hop_length=_HOP_LENGTH)
    est = _tempo(
        np.asarray(env, dtype=np.float64), sr, _HOP_LENGTH, min_bpm=min_bpm, max_bpm=max_bpm
    )
    return est.bpm, est.confidence


def rms_series(
    samples: np.ndarray, sr: int, *, window_s: float = 0.4, hop_s: float = 0.2
) -> tuple[np.ndarray, np.ndarray]:
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
    from scipy.signal import butter, sosfiltfilt

    low, high = band_hz
    nyquist = sr / 2.0
    if low <= 0 and high >= nyquist:
        filtered = samples
    elif low <= 0:
        sos = butter(4, high, btype="lowpass", fs=sr, output="sos")
        filtered = sosfiltfilt(sos, samples).astype(np.float32)
    elif high >= nyquist:
        sos = butter(4, low, btype="highpass", fs=sr, output="sos")
        filtered = sosfiltfilt(sos, samples).astype(np.float32)
    else:
        sos = butter(4, (low, high), btype="bandpass", fs=sr, output="sos")
        filtered = sosfiltfilt(sos, samples).astype(np.float32)
    return rms_series(filtered, sr, window_s=window_s, hop_s=hop_s)


def _to_db(linear: float) -> float:
    return 20.0 * float(np.log10(max(linear, 1e-10)))


def segment_boundaries(
    segment_start_s: list[float], segment_lengths_s: list[float], total_duration: float
) -> list[float]:
    points = {0.0, total_duration}
    for start, length in zip(segment_start_s, segment_lengths_s, strict=False):
        end = start + length
        if 0.0 < end < total_duration:
            points.add(round(end, 3))
    return sorted(points)


from app.domain.render.models import RenderPlan as _RenderPlan


def build_verify_manifest(
    inputs: list[Any], plan: _RenderPlan, grid: dict[int, Any]
) -> DJManifest:
    sources = [
        DJSource(
            track_id=ti.track_id,
            file_path=ti.file_path,
            title=ti.title,
            bpm=ti.bpm,
            key_code=ti.key_code,
        )
        for ti in inputs
    ]
    return DJManifest(
        version_id=0,
        target_bpm=plan.target_bpm,
        sources=sources,
        n_segments=plan.n,
        expected_duration_s=plan.segments[-1].start_s + plan.segments[-1].length_s
        if plan.segments
        else 0.0,
        segment_start_s=[s.start_s for s in plan.segments],
        segment_lengths_s=[s.length_s for s in plan.segments],
    )


# ── measurements ──────────────────────────────────────────────────────


@dataclass(slots=True)
class SourceMeasure:
    path: str
    exists: bool = False
    decoded_duration: float | None = None
    bpm: float | None = None
    bpm_confidence: float | None = None


@dataclass(slots=True)
class OutputMeasure:
    path: str
    exists: bool = False
    decoded_duration: float | None = None
    rms_times: np.ndarray | None = None
    rms_db: np.ndarray | None = None
    low_rms_times: np.ndarray | None = None
    low_rms_db: np.ndarray | None = None
    bpm: float | None = None
    bpm_confidence: float | None = None
    sample_peak_db: float | None = None
    clipped_sample_count: int = 0
    first_clip_time: float | None = None
    channel_rms_db: tuple[float, float] | None = None
    stereo_correlation: float | None = None
    segments: list[tuple[float, float, float | None]] = field(default_factory=list)
    energy_slope_db_per_min: float | None = None
    rms_jumps_per_min: float | None = None
    rms_jump_times: list[tuple[float, float]] = field(default_factory=list)
    energy_dip_count: int = 0
    energy_dip_times: list[tuple[float, float]] = field(default_factory=list)


def measure_source(
    path: str, *, bpm_hint: float | None, min_bpm: float = 100.0, max_bpm: float = 200.0
) -> SourceMeasure:
    m = SourceMeasure(path=path)
    if not Path(path).is_file():
        return m
    m.exists = True
    samples, sr = load_audio(path)
    m.decoded_duration = len(samples) / sr
    m.bpm, m.bpm_confidence = estimate_bpm(samples, sr, min_bpm=min_bpm, max_bpm=max_bpm)
    return m


def _segment_lufs(path: str, start_s: float, duration_s: float) -> float | None:
    import re

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
                path,
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
    match = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", proc.stderr)
    return float(match[-1]) if match else None


def _stereo_summary(channels: np.ndarray) -> tuple[tuple[float, float] | None, float | None]:
    if channels.ndim != 2 or channels.shape[0] < 2 or channels.shape[1] == 0:
        return None, None
    left = channels[0].astype(np.float64)
    right = channels[1].astype(np.float64)
    left_db = _to_db(float(np.sqrt(np.mean(np.square(left)))))
    right_db = _to_db(float(np.sqrt(np.mean(np.square(right)))))
    corr = None
    if float(np.std(left)) > 1e-9 and float(np.std(right)) > 1e-9:
        corr = float(np.corrcoef(left, right)[0, 1])
    return (left_db, right_db), corr


def _true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
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


def measure_output(
    path: str,
    segment_boundaries: list[float],
    *,
    min_bpm: float = 100.0,
    max_bpm: float = 200.0,
    min_segment_s: float = 3.0,
) -> OutputMeasure:
    m = OutputMeasure(path=path)
    if not Path(path).is_file():
        return m
    m.exists = True

    channels, sr_int = load_audio_stereo(path)
    out_samples = np.mean(channels, axis=0).astype(np.float64)
    m.decoded_duration = len(out_samples) / sr_int

    m.rms_times, m.rms_db = rms_series(out_samples, sr_int)
    m.low_rms_times, m.low_rms_db = band_rms_series(out_samples, sr_int, (25.0, 150.0))

    peak = float(np.max(np.abs(channels))) if channels.size else 0.0
    m.sample_peak_db = _to_db(peak)
    m.clipped_sample_count = int(np.count_nonzero(np.abs(channels) >= 0.999))
    if m.clipped_sample_count > 0:
        clip_mask = np.any(np.abs(channels) >= 0.999, axis=0)
        m.first_clip_time = int(np.argmax(clip_mask)) / sr_int
    m.channel_rms_db, m.stereo_correlation = _stereo_summary(channels)

    for start, end in itertools.pairwise(segment_boundaries):
        if end - start < min_segment_s:
            continue
        m.segments.append((start, end, _segment_lufs(path, start, end - start)))

    m.bpm, m.bpm_confidence = estimate_bpm(out_samples, sr_int, min_bpm=min_bpm, max_bpm=max_bpm)

    # Energy slope
    total_s = m.decoded_duration
    if m.rms_db is not None and len(m.rms_db) > 20:
        hop_s = float(m.rms_times[1] - m.rms_times[0]) if len(m.rms_times) >= 2 else 0.2
        win = max(1, int(10.0 / hop_s))
        smooth = np.convolve(m.rms_db, np.ones(win) / win, mode="valid")
        t = np.arange(len(smooth), dtype=np.float64) * hop_s / 60.0
        if len(t) >= 3:
            coeffs = np.polyfit(t, smooth, deg=1)
            m.energy_slope_db_per_min = float(coeffs[0])

    # RMS jumps
    if m.rms_db is not None and len(m.rms_db) > 10:
        hop_s = float(m.rms_times[1] - m.rms_times[0]) if len(m.rms_times) >= 2 else 0.2
        win = max(1, int(3.0 / hop_s))
        smooth = np.convolve(m.rms_db, np.ones(win) / win, mode="valid")
        diffs = np.diff(smooth)
        jump_mask = np.abs(diffs) > 9.0
        jumps = int(np.sum(jump_mask))
        m.rms_jumps_per_min = jumps / (total_s / 60.0) if total_s > 0 else 0.0
        jump_indices = np.where(jump_mask)[0]
        pad = win // 2
        m.rms_jump_times = [
            (float(m.rms_times[min(idx + pad, len(m.rms_times) - 1)]), float(diffs[idx]))
            for idx in jump_indices[:20]
        ]

    # Energy dips
    if m.rms_db is not None and len(m.rms_db) > 2:
        hop_s = float(m.rms_times[1] - m.rms_times[0]) if len(m.rms_times) >= 2 else 0.2
        window_len = max(1, int(3.0 / hop_s))
        mean_linear = float(np.mean(10.0 ** (m.rms_db / 20.0)))
        dip_threshold = mean_linear * 0.3
        short_rms = np.convolve(
            10.0 ** (m.rms_db / 20.0), np.ones(window_len) / window_len, mode="valid"
        )
        below = short_rms < dip_threshold
        min_dip_frames = max(1, int(5.0 / hop_s))
        gaps = np.diff(np.concatenate(([False], below, [False]))).astype(int)
        onsets = np.where(gaps == 1)[0]
        offsets = np.where(gaps == -1)[0]
        for i in range(min(len(onsets), len(offsets))):
            if (offsets[i] - onsets[i]) >= min_dip_frames:
                ts = float(m.rms_times[min(onsets[i], len(m.rms_times) - 1)])
                te = float(m.rms_times[min(offsets[i], len(m.rms_times) - 1)])
                m.energy_dip_times.append((ts, te))
        m.energy_dip_count = len(m.energy_dip_times)

    return m
