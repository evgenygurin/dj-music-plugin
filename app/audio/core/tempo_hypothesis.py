"""Compatibility tempo-lattice helpers retained for legacy audio tests."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class TempoHypothesis:
    bpm: float
    multiplier: float
    lag_frames: float
    confidence: float
    dominance_ratio: float


@dataclass(frozen=True, slots=True)
class TempoLattice:
    hypotheses: tuple[TempoHypothesis, ...]

    @property
    def dominant(self) -> TempoHypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None

    @property
    def ambiguous(self) -> bool:
        return len(self.hypotheses) > 1 and self.hypotheses[1].confidence >= self.hypotheses[0].confidence * 0.8

    def hypothesis_for_multiplier(self, multiplier: float) -> TempoHypothesis | None:
        return next((h for h in self.hypotheses if h.multiplier == multiplier), None)

    def to_dict(self) -> dict[str, object]:
        return {
            "hypotheses": [
                {
                    "bpm": h.bpm,
                    "multiplier": h.multiplier,
                    "lag_frames": h.lag_frames,
                    "confidence": h.confidence,
                    "dominance_ratio": h.dominance_ratio,
                }
                for h in self.hypotheses
            ],
            "ambiguous": self.ambiguous,
        }


def extract_tempo_lattice(acf: np.ndarray, frames_per_sec: float) -> TempoLattice:
    if len(acf) < 4 or frames_per_sec <= 0:
        return TempoLattice(())
    indices = np.arange(1, len(acf))
    bpms = 60.0 * frames_per_sec / indices
    allowed = (bpms >= 100.0) & (bpms <= 200.0)
    if not np.any(allowed):
        return TempoLattice(())
    base_lag = int(indices[allowed][int(np.argmax(acf[indices[allowed]]))])
    candidates: list[TempoHypothesis] = []
    for multiplier, lag in ((1.0, base_lag), (0.5, base_lag * 2), (2.0, max(1, base_lag // 2))):
        if lag >= len(acf):
            continue
        value = float(acf[lag])
        if value > 0:
            candidates.append(TempoHypothesis(float(60.0 * frames_per_sec / lag), multiplier, float(lag), value, value))
    candidates.sort(key=lambda h: h.confidence, reverse=True)
    return TempoLattice(tuple(candidates))


def resolve_dominant_bpm(lattice: TempoLattice) -> float:
    return lattice.dominant.bpm if lattice.dominant else 0.0
