"""Backward-compatible adapter for the canonical :mod:`.tempo` BeatGrid.

New analysis code uses ``app.audio.core.tempo.BeatGrid``.  This module keeps
the small historical array-oriented API importable for audio callers while
delegating its data shape to that canonical representation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class BeatGrid:
    bpm: float
    beat_times: np.ndarray
    beats_per_bar: int = 4
    confidence: float = 0.0
    stability: float = 0.0
    tempo_curve_times: np.ndarray | None = None
    tempo_curve_bpm: np.ndarray | None = None

    @classmethod
    def empty(cls) -> BeatGrid:
        return cls(0.0, np.array([], dtype=np.float64))

    @classmethod
    def from_arrays(
        cls,
        *,
        beat_times: np.ndarray,
        bpm: float,
        beats_per_bar: int = 4,
        confidence: float = 0.0,
        stability: float = 0.0,
        tempo_curve_times: np.ndarray | None = None,
        tempo_curve_bpm: np.ndarray | None = None,
    ) -> BeatGrid:
        if tempo_curve_times is not None and tempo_curve_bpm is not None and len(tempo_curve_times) != len(tempo_curve_bpm):
            raise ValueError("tempo_curve_times and tempo_curve_bpm must have equal length")
        return cls(
            float(bpm), np.asarray(beat_times, dtype=np.float64), max(1, int(beats_per_bar)),
            float(np.clip(confidence, 0.0, 1.0)), float(np.clip(stability, 0.0, 1.0)),
            None if tempo_curve_times is None else np.asarray(tempo_curve_times, dtype=np.float64),
            None if tempo_curve_bpm is None else np.asarray(tempo_curve_bpm, dtype=np.float64),
        )

    @property
    def is_valid(self) -> bool:
        return self.bpm > 0 and self.num_beats >= 2

    @property
    def num_beats(self) -> int:
        return len(self.beat_times)

    @property
    def num_bars(self) -> int:
        return self.num_beats // self.beats_per_bar

    @property
    def beat_array_s(self) -> np.ndarray:
        return self.beat_times

    @property
    def downbeat_times(self) -> np.ndarray:
        return self.beat_times[: self.num_bars * self.beats_per_bar : self.beats_per_bar]

    @property
    def bar_starts_s(self) -> np.ndarray:
        return self.downbeat_times

    @property
    def phase(self) -> float:
        return 0.0

    def nearest_beat(self, t_s: float) -> int:
        if not self.num_beats:
            return -1
        return int(np.argmin(np.abs(self.beat_times - t_s)))

    def bpm_at(self, t_s: float) -> float:
        if self.tempo_curve_times is None or self.tempo_curve_bpm is None or not len(self.tempo_curve_times):
            return self.bpm
        return float(np.interp(t_s, self.tempo_curve_times, self.tempo_curve_bpm))

    def to_dict(self) -> dict[str, object]:
        return {
            "bpm": self.bpm, "num_beats": self.num_beats, "num_bars": self.num_bars,
            "beat_times": self.beat_times.tolist(), "downbeat_times": self.downbeat_times.tolist(),
            "tempo_hypothesis": 1.0,
        }
