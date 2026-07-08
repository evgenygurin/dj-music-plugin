from __future__ import annotations

import numpy as np
import numpy.typing as npt

from app.domain.transition.kernels.bpm_distance import bpm_distance, bpm_distance_bulk
from app.domain.transition.kernels.cosine import cosine_similarity_bulk
from app.domain.transition.kernels.gauss import gauss_similarity
from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.shared.features import TrackFeatures


class DrumsComponent:
    name = "drums"
    default_weight = 0.20

    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        components: list[float] = []
        weights: list[float] = []

        if from_t.bpm is not None and to_t.bpm is not None:
            delta = bpm_distance(from_t.bpm, to_t.bpm)
            sigma = 3.0
            score = gauss_similarity(delta, sigma)
            if from_t.bpm_stability is not None and to_t.bpm_stability is not None:
                stability = min(from_t.bpm_stability, to_t.bpm_stability)
                score *= max(0.7, stability)
            components.append(score)
            weights.append(0.50)
        else:
            components.append(0.5)
            weights.append(0.50)

        if from_t.kick_prominence is not None and to_t.kick_prominence is not None:
            diff = abs(from_t.kick_prominence - to_t.kick_prominence)
            components.append(max(0.0, 1.0 - diff))
            weights.append(0.25)

        if from_t.onset_rate is not None and to_t.onset_rate is not None:
            max_rate = max(from_t.onset_rate, to_t.onset_rate, 1.0)
            components.append(max(0.0, 1.0 - abs(from_t.onset_rate - to_t.onset_rate) / max_rate))
            weights.append(0.15)

        if from_t.beat_loudness_band_ratio and to_t.beat_loudness_band_ratio:
            components.append(
                _scalar_cosine(from_t.beat_loudness_band_ratio, to_t.beat_loudness_band_ratio)
            )
            weights.append(0.10)

        return _weighted_average(components, weights)

    def score_pairs(
        self, fa: FeatureArrays, ia: npt.NDArray[np.int64], ib: npt.NDArray[np.int64]
    ) -> npt.NDArray[np.float64]:
        bpm_a = fa.bpm[ia]
        bpm_b = fa.bpm[ib]
        bpm_present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))
        delta = bpm_distance_bulk(bpm_a, bpm_b)
        bpm_score = np.exp(-(delta**2) / (2 * 3.0**2))
        stab_a = fa.bpm_stability[ia]
        stab_b = fa.bpm_stability[ib]
        stab_present = ~(np.isnan(stab_a) | np.isnan(stab_b))
        stab_factor = np.where(stab_present, np.maximum(0.7, np.minimum(stab_a, stab_b)), 1.0)
        bpm_score = bpm_score * stab_factor
        bpm_term = np.where(bpm_present, bpm_score, 0.5)
        weight_bpm = np.full_like(bpm_term, 0.50)

        kick_a = fa.kick_prominence[ia]
        kick_b = fa.kick_prominence[ib]
        kick_present = ~(np.isnan(kick_a) | np.isnan(kick_b))
        kick_term = np.where(kick_present, np.maximum(0.0, 1.0 - np.abs(kick_a - kick_b)), 0.0)
        weight_kick = np.where(kick_present, 0.25, 0.0)

        onset_a = fa.onset_rate[ia]
        onset_b = fa.onset_rate[ib]
        onset_present = ~(np.isnan(onset_a) | np.isnan(onset_b))
        max_rate = np.maximum(np.maximum(onset_a, onset_b), 1.0)
        onset_term = np.where(
            onset_present,
            np.maximum(0.0, 1.0 - np.abs(onset_a - onset_b) / max_rate),
            0.0,
        )
        weight_onset = np.where(onset_present, 0.15, 0.0)

        bl_present = fa.beat_loudness_present[ia] & fa.beat_loudness_present[ib]
        bl_cos = cosine_similarity_bulk(fa.beat_loudness, ia, ib)
        bl_term = np.where(bl_present, bl_cos, 0.0)
        weight_bl = np.where(bl_present, 0.10, 0.0)

        numerator = (
            bpm_term * weight_bpm
            + kick_term * weight_kick
            + onset_term * weight_onset
            + bl_term * weight_bl
        )
        denominator = weight_bpm + weight_kick + weight_onset + weight_bl
        return np.where(denominator > 0, numerator / denominator, 0.5)


def _weighted_average(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.5
    total_w = sum(weights)
    if total_w == 0:
        return 0.5
    return sum(v * w for v, w in zip(values, weights, strict=False)) / total_w


def _scalar_cosine(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x**2 for x in a))
    norm_b = math.sqrt(sum(x**2 for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, (dot / (norm_a * norm_b) + 1) / 2))
