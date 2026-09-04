"""Legacy/new transition parity diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShadowComparison:
    technical_parity: bool
    score_delta: float

    @classmethod
    def compare(
        cls, legacy_candidate: str, new_candidate: str, legacy_score: float, new_score: float
    ) -> ShadowComparison:
        return cls(legacy_candidate == new_candidate, new_score - legacy_score)
