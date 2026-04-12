"""Spectral / timbral-balance scoring.

Six sub-signals (MFCC cosine, centroid, energy bands correlation,
rolloff similarity, slope, flux std) collapsed by their per-feature
weights, then penalised when both tracks are dissonant or differ in
spectral complexity.
"""

from __future__ import annotations

from dj_music.schemas.audio import TrackFeatures
from dj_music.transition.math_helpers import correlation, cosine_similarity
from dj_music.transition.weights import (
    COMPLEXITY_DIFF_THRESHOLD,
    COMPLEXITY_PENALTY,
    DISSONANCE_PAIR_THRESHOLD,
    DISSONANCE_PENALTY,
    SPECTRAL_SUB_WEIGHTS,
)


def score_spectral(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """Score spectral / timbral similarity. Range [0, 1]."""
    signals: list[float] = []
    weights: list[float] = []

    # MFCC cosine similarity
    if from_t.mfcc_vector and to_t.mfcc_vector:
        signals.append(cosine_similarity(from_t.mfcc_vector, to_t.mfcc_vector))
        weights.append(SPECTRAL_SUB_WEIGHTS["mfcc"])

    # Centroid proximity
    if from_t.spectral_centroid_hz is not None and to_t.spectral_centroid_hz is not None:
        max_c = max(from_t.spectral_centroid_hz, to_t.spectral_centroid_hz, 1.0)
        centroid_sim = max(
            0.0, 1.0 - abs(from_t.spectral_centroid_hz - to_t.spectral_centroid_hz) / max_c
        )
        signals.append(centroid_sim)
        weights.append(SPECTRAL_SUB_WEIGHTS["centroid"])

    # Energy band balance
    if from_t.energy_bands and to_t.energy_bands:
        signals.append(max(0.0, correlation(from_t.energy_bands, to_t.energy_bands)))
        weights.append(SPECTRAL_SUB_WEIGHTS["energy_bands"])

    # Rolloff similarity (averaged over both rolloff points)
    rolloff_sims: list[float] = []
    if from_t.spectral_rolloff_85 is not None and to_t.spectral_rolloff_85 is not None:
        max_r = max(from_t.spectral_rolloff_85, to_t.spectral_rolloff_85, 1.0)
        rolloff_sims.append(
            max(0.0, 1.0 - abs(from_t.spectral_rolloff_85 - to_t.spectral_rolloff_85) / max_r)
        )
    if from_t.spectral_rolloff_95 is not None and to_t.spectral_rolloff_95 is not None:
        max_r = max(from_t.spectral_rolloff_95, to_t.spectral_rolloff_95, 1.0)
        rolloff_sims.append(
            max(0.0, 1.0 - abs(from_t.spectral_rolloff_95 - to_t.spectral_rolloff_95) / max_r)
        )
    if rolloff_sims:
        signals.append(sum(rolloff_sims) / len(rolloff_sims))
        weights.append(SPECTRAL_SUB_WEIGHTS["rolloff"])

    # Spectral slope similarity
    if from_t.spectral_slope is not None and to_t.spectral_slope is not None:
        max_s = max(abs(from_t.spectral_slope), abs(to_t.spectral_slope), 1e-9)
        slope_sim = max(0.0, 1.0 - abs(from_t.spectral_slope - to_t.spectral_slope) / max_s)
        signals.append(slope_sim)
        weights.append(SPECTRAL_SUB_WEIGHTS["slope"])

    # Flux std similarity
    if from_t.spectral_flux_std is not None and to_t.spectral_flux_std is not None:
        max_f = max(from_t.spectral_flux_std, to_t.spectral_flux_std, 1e-9)
        flux_sim = max(0.0, 1.0 - abs(from_t.spectral_flux_std - to_t.spectral_flux_std) / max_f)
        signals.append(flux_sim)
        weights.append(SPECTRAL_SUB_WEIGHTS["flux"])

    score = (
        sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)
        if weights
        else 0.5
    )

    # Dissonance penalty: two harsh tracks together = muddy mix
    if (
        from_t.dissonance_mean is not None
        and to_t.dissonance_mean is not None
        and from_t.dissonance_mean > DISSONANCE_PAIR_THRESHOLD
        and to_t.dissonance_mean > DISSONANCE_PAIR_THRESHOLD
    ):
        score = max(0.0, score - DISSONANCE_PENALTY)

    # Spectral complexity penalty: two complex tracks = clutter
    if (
        from_t.spectral_complexity_mean is not None and to_t.spectral_complexity_mean is not None
    ) and abs(
        from_t.spectral_complexity_mean - to_t.spectral_complexity_mean
    ) > COMPLEXITY_DIFF_THRESHOLD:
        score = max(0.0, score - COMPLEXITY_PENALTY)

    return score
