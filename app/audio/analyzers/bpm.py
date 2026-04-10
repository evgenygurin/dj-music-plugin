"""BPM detector — librosa-based tempo analysis.

Computes: bpm, bpm_confidence, bpm_stability, variable_tempo.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.rhythm import find_beat_times, tempo_from_onset_autocorrelation


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
        import librosa  # noqa: F401

        sr = ctx.sr
        hop_length = ctx.params.hop_length

        # Onset envelope (cached, shared with beat/tempogram analyzers)
        onset_env = ctx.get_onset_env()

        estimate = tempo_from_onset_autocorrelation(onset_env, sr, hop_length)
        bpm = estimate.bpm
        confidence = estimate.confidence
        beat_times = find_beat_times(onset_env, sr, hop_length, bpm_hint=bpm)

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
    estimate = tempo_from_onset_autocorrelation(
        onset_env,
        sr,
        hop_length,
        min_bpm=min_bpm,
        max_bpm=max_bpm,
    )
    return estimate.bpm
