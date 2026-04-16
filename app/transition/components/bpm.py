"""BPM compatibility scoring.

Gaussian similarity around the BPM distance (with double/half-time
awareness) plus penalties for unstable / variable tempo and low BPM
detection confidence.
"""

from __future__ import annotations

import math

from app.config import settings
from app.entities.audio.features import TrackFeatures
from app.transition.constants import (
    BPM_CONFIDENCE_PENALTY_FLOOR,
    BPM_GAUSS_SIGMA,
    BPM_STABILITY_FLOOR,
)
from app.transition.math_helpers import bpm_distance


def score_bpm(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Score BPM compatibility between two tracks. Range [0, 1]."""
    if from_t.bpm is None or to_t.bpm is None:
        return 0.5  # unknown = neutral
    delta = bpm_distance(from_t.bpm, to_t.bpm)
    score = math.exp(-(delta**2) / (2 * BPM_GAUSS_SIGMA**2))

    # BPM stability factor: unstable tempo makes mixing harder
    if from_t.bpm_stability is not None and to_t.bpm_stability is not None:
        stability = min(from_t.bpm_stability, to_t.bpm_stability)
        score *= max(BPM_STABILITY_FLOOR, stability)

    # BPM confidence factor: low confidence reduces score
    if from_t.bpm_confidence is not None and to_t.bpm_confidence is not None:
        min_conf = min(from_t.bpm_confidence, to_t.bpm_confidence)
        if min_conf < settings.scoring_bpm_confidence_floor:
            score *= max(
                BPM_CONFIDENCE_PENALTY_FLOOR,
                min_conf / settings.scoring_bpm_confidence_floor,
            )

    # Variable tempo penalty: hard to mix variable-tempo tracks
    if (from_t.variable_tempo is True) or (to_t.variable_tempo is True):
        score = max(0.0, score - settings.scoring_variable_tempo_penalty)

    return score
