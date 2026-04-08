"""Groove / rhythm compatibility scoring.

Onset density, kick prominence, beat-loudness band ratio cosine, pulse
clarity, harmonic-percussive ratio, and tempogram cosine — averaged by
their per-feature weights.
"""

from __future__ import annotations

from app.core.track_features import TrackFeatures
from app.transition.math_helpers import cosine_similarity
from app.transition.weights import GROOVE_SUB_WEIGHTS


def score_groove(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Score groove / rhythm similarity. Range [0, 1]."""
    signals: list[float] = []
    weights: list[float] = []

    if from_t.onset_rate is not None and to_t.onset_rate is not None:
        max_rate = max(from_t.onset_rate, to_t.onset_rate, 1.0)
        signals.append(max(0.0, 1.0 - abs(from_t.onset_rate - to_t.onset_rate) / max_rate))
        weights.append(GROOVE_SUB_WEIGHTS["onset_rate"])

    if from_t.kick_prominence is not None and to_t.kick_prominence is not None:
        signals.append(max(0.0, 1.0 - abs(from_t.kick_prominence - to_t.kick_prominence)))
        weights.append(GROOVE_SUB_WEIGHTS["kick_prominence"])

    if from_t.beat_loudness_band_ratio and to_t.beat_loudness_band_ratio:
        signals.append(
            cosine_similarity(from_t.beat_loudness_band_ratio, to_t.beat_loudness_band_ratio)
        )
        weights.append(GROOVE_SUB_WEIGHTS["beat_loudness"])

    if from_t.pulse_clarity is not None and to_t.pulse_clarity is not None:
        signals.append(max(0.0, 1.0 - abs(from_t.pulse_clarity - to_t.pulse_clarity)))
        weights.append(GROOVE_SUB_WEIGHTS["pulse_clarity"])

    if from_t.hp_ratio is not None and to_t.hp_ratio is not None:
        max_hp = max(from_t.hp_ratio, to_t.hp_ratio, 1e-9)
        signals.append(max(0.0, 1.0 - abs(from_t.hp_ratio - to_t.hp_ratio) / max_hp))
        weights.append(GROOVE_SUB_WEIGHTS["hp_ratio"])

    if from_t.tempogram_ratio_vector and to_t.tempogram_ratio_vector:
        signals.append(
            cosine_similarity(from_t.tempogram_ratio_vector, to_t.tempogram_ratio_vector)
        )
        weights.append(GROOVE_SUB_WEIGHTS["tempogram"])

    if not weights:
        return 0.5

    return sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)
