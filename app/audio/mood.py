"""Mood classifier — rule-based subgenre classification.

Scores each track against 15 techno subgenre profiles using audio features.
No ML model — pure weighted scoring with hand-tuned weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.core.constants import TechnoSubgenre


@dataclass
class MoodResult:
    """Result of mood classification."""

    mood: TechnoSubgenre
    confidence: float
    scores: dict[TechnoSubgenre, float] = field(default_factory=dict)
    reasoning: str = ""


# Subgenre scoring profiles: feature_name -> (weight, ideal_value, tolerance)
# Score for each feature = weight * exp(-(value - ideal)^2 / (2 * tolerance^2))
SUBGENRE_PROFILES: dict[TechnoSubgenre, dict[str, tuple[float, float, float]]] = {
    TechnoSubgenre.AMBIENT_DUB: {
        "energy_mean": (2.0, 0.1, 0.1),
        "spectral_centroid_hz": (1.5, 800.0, 500.0),
        "spectral_flatness": (1.0, 0.15, 0.1),
        "spectral_flux_std": (1.0, 0.5, 0.5),
        "loudness_range_lu": (1.5, 12.0, 5.0),
        "crest_factor_db": (1.0, 15.0, 5.0),
    },
    TechnoSubgenre.DUB_TECHNO: {
        "energy_mean": (1.5, 0.2, 0.1),
        "spectral_centroid_hz": (1.5, 1200.0, 600.0),
        "spectral_flatness": (1.0, 0.2, 0.1),
        "loudness_range_lu": (2.0, 10.0, 4.0),
        "energy_low": (1.5, 0.3, 0.15),
        "spectral_flux_std": (1.0, 1.0, 1.0),
    },
    TechnoSubgenre.MINIMAL: {
        "energy_mean": (1.5, 0.25, 0.1),
        "spectral_centroid_hz": (1.0, 1500.0, 700.0),
        "spectral_flatness": (1.5, 0.1, 0.08),
        "energy_std": (1.5, 0.1, 0.08),
        "spectral_flux_std": (1.0, 0.8, 0.5),
        "energy_mid": (1.0, 0.15, 0.1),
    },
    TechnoSubgenre.DETROIT: {
        "energy_mean": (1.5, 0.4, 0.15),
        "spectral_centroid_hz": (1.5, 2000.0, 800.0),
        "energy_mid": (1.5, 0.2, 0.1),
        "spectral_flux_mean": (1.0, 5.0, 3.0),
        "crest_factor_db": (1.0, 10.0, 4.0),
        "energy_highmid": (1.0, 0.15, 0.1),
    },
    TechnoSubgenre.MELODIC_DEEP: {
        "energy_mean": (1.0, 0.35, 0.15),
        "spectral_centroid_hz": (2.0, 1200.0, 500.0),
        "spectral_flatness": (1.5, 0.08, 0.05),
        "energy_mid": (1.5, 0.25, 0.1),
        "loudness_range_lu": (1.0, 8.0, 3.0),
        "spectral_flux_std": (1.0, 2.0, 1.5),
    },
    TechnoSubgenre.PROGRESSIVE: {
        "energy_mean": (1.0, 0.4, 0.15),
        "energy_slope": (2.0, 0.001, 0.001),
        "spectral_centroid_hz": (1.0, 2000.0, 800.0),
        "energy_std": (1.5, 0.2, 0.1),
        "spectral_flux_mean": (1.0, 5.0, 3.0),
        "loudness_range_lu": (1.0, 8.0, 3.0),
    },
    TechnoSubgenre.HYPNOTIC: {
        "energy_mean": (1.0, 0.45, 0.15),
        "spectral_flux_std": (2.0, 0.5, 0.4),
        "energy_std": (2.0, 0.05, 0.04),
        "spectral_centroid_hz": (1.0, 1800.0, 700.0),
        "spectral_flatness": (1.0, 0.12, 0.08),
        "energy_low": (1.0, 0.25, 0.1),
    },
    TechnoSubgenre.DRIVING: {
        "energy_mean": (1.5, 0.55, 0.15),
        "spectral_centroid_hz": (1.0, 2500.0, 1000.0),
        "energy_low": (1.5, 0.25, 0.1),
        "spectral_flux_mean": (1.0, 8.0, 4.0),
        "crest_factor_db": (1.0, 8.0, 3.0),
        "energy_std": (1.0, 0.12, 0.08),
    },
    TechnoSubgenre.TRIBAL: {
        "energy_mean": (1.5, 0.5, 0.15),
        "spectral_centroid_hz": (1.0, 1800.0, 700.0),
        "energy_low": (2.0, 0.3, 0.12),
        "energy_sub": (1.5, 0.15, 0.08),
        "spectral_flux_std": (1.0, 3.0, 2.0),
        "energy_std": (1.0, 0.15, 0.1),
    },
    TechnoSubgenre.BREAKBEAT: {
        "energy_mean": (1.0, 0.5, 0.15),
        "spectral_flux_std": (2.0, 8.0, 4.0),
        "energy_std": (2.0, 0.25, 0.1),
        "spectral_centroid_hz": (1.0, 2500.0, 1000.0),
        "crest_factor_db": (1.0, 12.0, 4.0),
        "energy_highmid": (1.0, 0.18, 0.08),
    },
    TechnoSubgenre.PEAK_TIME: {
        "energy_mean": (2.0, 0.7, 0.15),
        "spectral_centroid_hz": (1.0, 3000.0, 1000.0),
        "energy_low": (1.5, 0.25, 0.1),
        "crest_factor_db": (1.0, 6.0, 3.0),
        "spectral_flux_mean": (1.0, 10.0, 5.0),
        "loudness_range_lu": (1.0, 5.0, 3.0),
    },
    TechnoSubgenre.ACID: {
        "spectral_centroid_hz": (2.5, 4000.0, 1500.0),
        "spectral_flatness": (1.5, 0.25, 0.1),
        "energy_mean": (1.0, 0.55, 0.15),
        "energy_highmid": (1.5, 0.22, 0.1),
        "spectral_flux_mean": (1.0, 8.0, 4.0),
        "spectral_rolloff_85": (1.0, 5000.0, 2000.0),
    },
    TechnoSubgenre.RAW: {
        "energy_mean": (1.5, 0.65, 0.15),
        "spectral_centroid_hz": (1.5, 3500.0, 1200.0),
        "spectral_flatness": (1.5, 0.3, 0.12),
        "crest_factor_db": (1.0, 5.0, 3.0),
        "loudness_range_lu": (1.0, 4.0, 2.0),
        "spectral_flux_std": (1.0, 5.0, 3.0),
    },
    TechnoSubgenre.INDUSTRIAL: {
        "energy_mean": (1.5, 0.75, 0.15),
        "spectral_centroid_hz": (1.5, 4000.0, 1500.0),
        "spectral_flatness": (2.0, 0.35, 0.12),
        "loudness_range_lu": (1.5, 3.0, 2.0),
        "crest_factor_db": (1.0, 4.0, 2.0),
        "energy_high": (1.0, 0.15, 0.08),
    },
    TechnoSubgenre.HARD_TECHNO: {
        "energy_mean": (2.0, 0.85, 0.1),
        "spectral_centroid_hz": (1.0, 3500.0, 1500.0),
        "energy_low": (1.5, 0.3, 0.12),
        "crest_factor_db": (1.0, 3.0, 2.0),
        "loudness_range_lu": (1.0, 3.0, 2.0),
        "spectral_flux_mean": (1.0, 12.0, 5.0),
    },
}

# Catch-all subgenres that get penalized
_CATCH_ALL_SUBGENRES = {TechnoSubgenre.DRIVING, TechnoSubgenre.HYPNOTIC}


class MoodClassifier:
    """Rule-based classifier for 15 techno subgenres."""

    def classify(self, features: dict[str, Any]) -> MoodResult:
        """Classify audio features into a techno subgenre.

        Args:
            features: Combined feature dict from pipeline analysis.

        Returns:
            MoodResult with winner, confidence, and all scores.
        """
        import numpy as np

        scores: dict[TechnoSubgenre, float] = {}

        for subgenre in TechnoSubgenre:
            scores[subgenre] = self._score_subgenre(subgenre, features)

        # Penalize catch-all subgenres to prevent domination
        for catch_all in _CATCH_ALL_SUBGENRES:
            scores[catch_all] *= settings.mood_catch_all_penalty

        # Find winner and compute confidence
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_scores[0][0]
        winner_score = sorted_scores[0][1]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0

        confidence = float((winner_score - second_score) / (winner_score + 1e-10))
        # Clamp to [0, 1]
        confidence = float(np.clip(confidence, 0.0, 1.0))

        reasoning = (
            f"Top match: {winner.value} (score={winner_score:.3f}), "
            f"runner-up: {sorted_scores[1][0].value} (score={second_score:.3f})"
        )

        return MoodResult(
            mood=winner,
            confidence=confidence,
            scores=scores,
            reasoning=reasoning,
        )

    def _score_subgenre(self, subgenre: TechnoSubgenre, features: dict[str, Any]) -> float:
        """Score features against a subgenre profile using Gaussian similarity."""
        import numpy as np

        profile = SUBGENRE_PROFILES.get(subgenre, {})
        if not profile:
            return 0.0

        total_score = 0.0
        total_weight = 0.0

        for feature_name, (weight, ideal, tolerance) in profile.items():
            value = features.get(feature_name)
            if value is None:
                continue

            # Gaussian similarity: exp(-(value - ideal)^2 / (2 * tolerance^2))
            diff = float(value) - ideal
            similarity = float(np.exp(-(diff**2) / (2.0 * tolerance**2)))

            total_score += weight * similarity
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return total_score / total_weight
