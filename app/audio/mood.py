"""Mood classifier — backward compatibility shim.

Re-exports from new locations in app.audio.classification.
TODO: Remove after all consumers updated (Task 10).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.audio.classification.classifier import MoodClassifier as _NewMoodClassifier
from app.audio.classification.classifier import MoodResult  # noqa: F401
from app.audio.classification.profiles import (
    ALL_PROFILES,
)
from app.audio.classification.profiles import (
    CATCH_ALL_SUBGENRES as _CATCH_ALL_SUBGENRES,  # noqa: F401 (backward compat alias)
)
from app.core.constants import TechnoSubgenre

# Re-create SUBGENRE_PROFILES dict in old format for backward compat with tests:
# dict[TechnoSubgenre, dict[str, tuple[float, float, float]]]
SUBGENRE_PROFILES: dict[TechnoSubgenre, dict[str, tuple[float, float, float]]] = {
    p.subgenre: {name: (t.weight, t.ideal, t.tolerance) for name, t in p.features.items()}
    for p in ALL_PROFILES
}


class MoodClassifier(_NewMoodClassifier):
    """Backward-compatible MoodClassifier.

    Extends the new classifier with _score_subgenre() that reads from
    the module-level SUBGENRE_PROFILES dict. This allows existing tests
    to patch SUBGENRE_PROFILES via patch.dict() and observe the effect.
    """

    def _score_subgenre(self, subgenre: TechnoSubgenre, features: dict[str, Any]) -> float:
        """Score features against a subgenre profile using Gaussian similarity.

        Reads from the module-level SUBGENRE_PROFILES dict so that
        patch.dict(SUBGENRE_PROFILES, ...) in tests affects the result.
        """
        profile = SUBGENRE_PROFILES.get(subgenre, {})
        if not profile:
            return 0.0

        total_score = 0.0
        total_weight = 0.0

        for feature_name, (weight, ideal, tolerance) in profile.items():
            value = features.get(feature_name)
            if value is None:
                continue

            diff = float(value) - ideal
            similarity = float(np.exp(-(diff**2) / (2.0 * tolerance**2)))

            total_score += weight * similarity
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return total_score / total_weight
