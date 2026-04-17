"""MoodClassifier — generic Gaussian scoring engine (Strategy pattern).

Classifier is generic; profiles are swappable via constructor injection.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.v2.config import get_settings
from app.v2.shared.constants import TechnoSubgenre

from .profiles import ALL_PROFILES, CATCH_ALL_SUBGENRES, SubgenreProfile


@dataclass
class MoodResult:
    """Result of mood classification."""

    mood: TechnoSubgenre
    confidence: float
    scores: dict[TechnoSubgenre, float] = field(default_factory=dict)
    reasoning: str = ""
    top_matches: list[tuple[TechnoSubgenre, float]] = field(default_factory=list)


class MoodClassifier:
    """Rule-based classifier for 15 techno subgenres (Strategy pattern).

    Profiles are injected via constructor — swappable for testing,
    custom genre sets, or A/B experiments.
    """

    def __init__(
        self,
        profiles: Sequence[SubgenreProfile] = ALL_PROFILES,
    ) -> None:
        self._profiles = profiles

    def classify(self, features: dict[str, Any]) -> MoodResult:
        """Classify audio features into a techno subgenre."""
        scores: dict[TechnoSubgenre, float] = {}

        for profile in self._profiles:
            scores[profile.subgenre] = self._score_profile(profile, features)

        # Penalize catch-all subgenres
        for subgenre in CATCH_ALL_SUBGENRES:
            if subgenre in scores:
                scores[subgenre] *= get_settings().audio.mood_catch_all_penalty

        # Find winner and compute confidence
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        winner = sorted_scores[0][0]
        winner_score = sorted_scores[0][1]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0

        confidence = float((winner_score - second_score) / (winner_score + 1e-10))
        confidence = float(np.clip(confidence, 0.0, 1.0))

        top_matches = [(sg, round(sc, 4)) for sg, sc in sorted_scores[:3]]

        reasoning = (
            f"Top match: {winner.value} (score={winner_score:.3f}), "
            f"runner-up: {sorted_scores[1][0].value} (score={second_score:.3f})"
        )

        return MoodResult(
            mood=winner,
            confidence=confidence,
            scores=scores,
            reasoning=reasoning,
            top_matches=top_matches,
        )

    def _score_profile(self, profile: SubgenreProfile, features: dict[str, Any]) -> float:
        """Score features against a profile using Gaussian similarity."""
        total_score = 0.0
        total_weight = 0.0

        for feature_name, target in profile.features.items():
            value = features.get(feature_name)
            if value is None:
                continue

            diff = float(value) - target.ideal
            similarity = float(np.exp(-(diff**2) / (2.0 * target.tolerance**2)))

            total_score += target.weight * similarity
            total_weight += target.weight

        if total_weight == 0:
            return 0.0

        return total_score / total_weight

    def _score_subgenre(self, subgenre: TechnoSubgenre, features: dict[str, Any]) -> float:
        """Backward compat — delegates to _score_profile."""
        for profile in self._profiles:
            if profile.subgenre == subgenre:
                return self._score_profile(profile, features)
        return 0.0
