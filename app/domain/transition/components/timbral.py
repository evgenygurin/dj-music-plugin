"""Timbral texture scoring.

Spectral contrast, pitch salience, danceability and dynamic complexity
— each normalised to [0, 1] over a domain-typical range, then averaged
by their per-feature weights.
"""

from __future__ import annotations

from app.core.track_features import TrackFeatures
from app.domain.transition.weights import (
    TIMBRAL_DANCEABILITY_NORM,
    TIMBRAL_DYNAMIC_COMPLEXITY_NORM,
    TIMBRAL_PITCH_SALIENCE_NORM,
    TIMBRAL_SPECTRAL_CONTRAST_NORM,
    TIMBRAL_SUB_WEIGHTS,
)


def score_timbral(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Score timbral texture similarity. Range [0, 1]."""
    signals: list[float] = []
    weights: list[float] = []

    if from_t.spectral_contrast is not None and to_t.spectral_contrast is not None:
        diff = abs(from_t.spectral_contrast - to_t.spectral_contrast)
        signals.append(max(0.0, 1.0 - diff / TIMBRAL_SPECTRAL_CONTRAST_NORM))
        weights.append(TIMBRAL_SUB_WEIGHTS["spectral_contrast"])

    if from_t.pitch_salience_mean is not None and to_t.pitch_salience_mean is not None:
        diff = abs(from_t.pitch_salience_mean - to_t.pitch_salience_mean)
        signals.append(max(0.0, 1.0 - diff / TIMBRAL_PITCH_SALIENCE_NORM))
        weights.append(TIMBRAL_SUB_WEIGHTS["pitch_salience"])

    if from_t.danceability is not None and to_t.danceability is not None:
        max_d = max(abs(from_t.danceability), abs(to_t.danceability), 1e-9)
        diff = abs(from_t.danceability - to_t.danceability)
        signals.append(max(0.0, 1.0 - diff / max(max_d, TIMBRAL_DANCEABILITY_NORM)))
        weights.append(TIMBRAL_SUB_WEIGHTS["danceability"])

    if from_t.dynamic_complexity is not None and to_t.dynamic_complexity is not None:
        diff = abs(from_t.dynamic_complexity - to_t.dynamic_complexity)
        signals.append(max(0.0, 1.0 - diff / TIMBRAL_DYNAMIC_COMPLEXITY_NORM))
        weights.append(TIMBRAL_SUB_WEIGHTS["dynamic_complexity"])

    if not signals:
        return 0.5  # neutral when unavailable

    return sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)
