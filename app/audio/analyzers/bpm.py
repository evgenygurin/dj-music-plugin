"""BPM detector — librosa-based tempo analysis.

Computes: bpm, bpm_confidence, bpm_stability, variable_tempo.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext


@register_analyzer
class BPMDetector(BaseAnalyzer):
    """Tempo detection using librosa beat tracking."""

    name: ClassVar[str] = "bpm"
    capabilities: ClassVar[frozenset[str]] = frozenset({"tempo", "rhythm"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    # beat_track + onset_strength scale linearly with audio length.
    # Techno BPM is stable across the whole track — 60s is sufficient.
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Detect BPM, confidence, and stability.

        BPM is computed via onset-strength autocorrelation with parabolic
        peak interpolation for sub-frame precision. With ``sr=22050`` and
        ``hop_length=512``, ``librosa.beat.beat_track`` and
        ``librosa.feature.tempo`` both round tempo to integer
        frames-per-beat, collapsing the techno range (120-140 BPM) into
        ~4 discrete values (123.05, 129.20, 136.00, ...). Parabolic
        interpolation around the autocorrelation peak recovers
        fractional-frame precision.
        """
        import librosa

        sr = ctx.sr
        hop_length = ctx.params.hop_length

        # Onset envelope (cached, shared with beat/tempogram analyzers)
        onset_env = ctx.get_onset_env()

        # Sub-frame BPM via autocorrelation peak interpolation
        bpm = _bpm_from_onset_autocorrelation(onset_env=onset_env, sr=sr, hop_length=hop_length)

        # Beat positions for stability metric (frame-quantized but fine here)
        _, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_env, sr=sr, hop_length=hop_length, units="frames"
        )
        beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)

        # Confidence from PLP mean (max is ~always 1.0 — meaningless as a signal)
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr, hop_length=hop_length)
        confidence = float(np.mean(pulse)) if len(pulse) > 0 else 0.5

        # Stability: how consistent are inter-beat intervals
        stability = 0.0
        variable_tempo = False
        if len(beat_times) > 2:
            ibis = np.diff(beat_times)
            if len(ibis) > 1 and np.mean(ibis) > 0:
                cv = float(np.std(ibis) / np.mean(ibis))
                stability = max(0.0, min(1.0, 1.0 - cv * 2))
                variable_tempo = cv > 0.15

        return {
            "bpm": round(bpm, 2),
            "bpm_confidence": round(min(1.0, confidence), 4),
            "bpm_stability": round(stability, 4),
            "variable_tempo": variable_tempo,
        }


def _bpm_from_onset_autocorrelation(
    onset_env: np.ndarray,
    sr: int,
    hop_length: int,
    min_bpm: float = 110.0,
    max_bpm: float = 200.0,
) -> float:
    """Compute BPM from onset envelope autocorrelation with sub-frame precision.

    Steps:
    1. Autocorrelate onset envelope (positive lags only)
    2. Restrict to lag range corresponding to ``[min_bpm, max_bpm]``
    3. Find peak lag (integer frames)
    4. Parabolic interpolation around the peak for sub-frame refinement
    5. Convert refined lag -> BPM

    ``min_bpm`` defaults to 110 because the workload is techno-only (lower
    bound of the genre is ~118 BPM; dub techno / deep sometimes dip to
    ~112). A lower floor was observed to cause half-tempo lock on
    peak-time techno: a 165 BPM track has a secondary autocorrelation
    peak at twice the lag (~83 BPM) because every other kick still
    aligns with the beat period, and on noisy / compressed MP3s that
    secondary peak can exceed the fundamental. Clamping ``max_lag`` to
    ~0.545 s (60 / 110) makes half-tempo physically unreachable within
    the search region for any true BPM above the floor. A production
    DB audit (bowosphlnghhgaulcyfm, L5 snapshot 2026-04-08) found 1097
    tracks locked to 80-84 BPM out of 5702 total — ~19% of the corpus
    was being misdetected as half-tempo before this fix.
    """
    if len(onset_env) < 4:
        return 0.0

    # Mean-center to keep autocorrelation peak at the actual rhythm period
    centered = onset_env - float(np.mean(onset_env))
    ac = np.correlate(centered, centered, mode="full")
    ac = ac[len(ac) // 2 :]  # keep positive lags

    frames_per_sec = sr / hop_length
    min_lag = max(1, int(np.floor(60.0 * frames_per_sec / max_bpm)))
    max_lag = min(len(ac) - 2, int(np.ceil(60.0 * frames_per_sec / min_bpm)))

    if max_lag <= min_lag + 1:
        return 0.0

    region = ac[min_lag : max_lag + 1]
    peak_offset = int(np.argmax(region))
    peak_idx = min_lag + peak_offset

    # Parabolic interpolation for sub-frame precision
    refined_lag = float(peak_idx)
    if 0 < peak_idx < len(ac) - 1:
        y_minus = float(ac[peak_idx - 1])
        y_zero = float(ac[peak_idx])
        y_plus = float(ac[peak_idx + 1])
        denom = y_minus - 2.0 * y_zero + y_plus
        if abs(denom) > 1e-12:
            offset = 0.5 * (y_minus - y_plus) / denom
            # Clamp interpolation offset to [-1, 1] for stability
            offset = max(-1.0, min(1.0, offset))
            refined_lag = peak_idx + offset

    if refined_lag <= 0:
        return 0.0
    return float(60.0 * frames_per_sec / refined_lag)
