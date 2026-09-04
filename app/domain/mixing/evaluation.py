"""Independent musical evaluators with explicit diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from .scores import DimensionScore, MusicalScore


@dataclass(frozen=True, slots=True)
class FeatureSet:
    harmony: float = 0.5
    energy: float = 0.5
    low_end: float = 0.5
    spectrum: float = 0.5
    groove: float = 0.5
    timbre: float = 0.5
    vocals: float = 0.0
    stems: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.harmony,
            self.energy,
            self.low_end,
            self.spectrum,
            self.groove,
            self.timbre,
            self.vocals,
            self.stems,
        )
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("feature values must be between 0 and 1")


_DEFAULT_WEIGHTS = {
    "harmony": 1.0,
    "energy": 1.0,
    "low_end": 1.0,
    "spectrum": 0.75,
    "groove": 1.0,
    "timbre": 0.75,
    "vocals": 1.0,
    "stems": 0.5,
}


class MusicalEvaluator:
    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = {**_DEFAULT_WEIGHTS, **(weights or {})}

    def evaluate(self, source: FeatureSet, target: FeatureSet) -> MusicalScore:
        similar = self._similar
        dimensions = (
            DimensionScore(
                "harmony", similar(source.harmony, target.harmony), self._weights["harmony"]
            ),
            DimensionScore(
                "energy", similar(source.energy, target.energy), self._weights["energy"]
            ),
            DimensionScore(
                "low_end",
                similar(source.low_end, target.low_end),
                self._weights["low_end"],
                "spectral",
            ),
            DimensionScore(
                "spectrum",
                similar(source.spectrum, target.spectrum),
                self._weights["spectrum"],
                "spectral",
            ),
            DimensionScore(
                "groove", similar(source.groove, target.groove), self._weights["groove"]
            ),
            DimensionScore(
                "timbre", similar(source.timbre, target.timbre), self._weights["timbre"]
            ),
            DimensionScore(
                "vocals", self._vocal_score(source.vocals, target.vocals), self._weights["vocals"]
            ),
            DimensionScore("stems", similar(source.stems, target.stems), self._weights["stems"]),
        )
        return MusicalScore(dimensions)

    @staticmethod
    def _similar(left: float, right: float) -> float:
        return max(0.0, 1.0 - abs(left - right))

    @staticmethod
    def _vocal_score(left: float, right: float) -> float:
        return max(0.0, 1.0 - left * right)
