"""Compatibility import path for the first-class beatgrid analyzer."""

from __future__ import annotations

import numpy as np

from app.audio.analyzers.beatgrid import BeatGridAnalyzer as _BeatGridAnalyzer


class BeatGridAnalyzer(_BeatGridAnalyzer):
    @staticmethod
    def _compute_phase(beat_times: np.ndarray, bpm: float) -> float:
        if len(beat_times) == 0 or bpm <= 0:
            return 0.0
        return float((beat_times[0] / (60.0 / bpm)) % 1.0)
