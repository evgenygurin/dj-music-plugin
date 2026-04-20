"""Energy / loudness flow scoring.

Gauss around a small preferred rise (+0.5 LUFS) on the LUFS delta with
optional penalties for inconsistent loudness range or crest factor and
a small bonus when both tracks share the same energy slope direction.
"""

from __future__ import annotations

import math

from app.config import get_settings
from app.domain.transition.features import TrackFeatures
from app.domain.transition.weights import (
    ENERGY_PREFERRED_RISE_LUFS,
    ENERGY_SIGMOID_DIVISOR,
)


def score_energy(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Score energy flow. Range [0, 1]."""
    settings = get_settings().transition
    if from_t.integrated_lufs is None or to_t.integrated_lufs is None:
        return 0.5
    delta = to_t.integrated_lufs - from_t.integrated_lufs
    # Gauss peaks at ENERGY_PREFERRED_RISE_LUFS (a tiny preferred rise,
    # under the 2 LUFS perceptual threshold) — equal loudness gives ~1.0,
    # symmetric decay for drops and big jumps.
    score = math.exp(
        -((delta - ENERGY_PREFERRED_RISE_LUFS) ** 2) / (2.0 * ENERGY_SIGMOID_DIVISOR**2)
    )

    # LRA penalty: large loudness range difference = inconsistent dynamics
    if from_t.loudness_range_lu is not None and to_t.loudness_range_lu is not None:
        lra_diff = abs(from_t.loudness_range_lu - to_t.loudness_range_lu)
        if lra_diff > settings.scoring_lra_diff_penalty_threshold:
            score = max(0.0, score - settings.scoring_lra_diff_penalty)

    # Crest factor penalty: large difference = very different dynamics
    if from_t.crest_factor_db is not None and to_t.crest_factor_db is not None:
        crest_diff = abs(from_t.crest_factor_db - to_t.crest_factor_db)
        if crest_diff > settings.scoring_crest_diff_penalty_threshold:
            score = max(0.0, score - settings.scoring_crest_diff_penalty)

    # Energy slope bonus: same direction = coherent energy arc
    if (
        from_t.energy_slope is not None
        and to_t.energy_slope is not None
        and (from_t.energy_slope > 0) == (to_t.energy_slope > 0)
    ):
        score = min(1.0, score + settings.scoring_energy_slope_bonus)

    return score
