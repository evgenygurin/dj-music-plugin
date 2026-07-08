from __future__ import annotations

import numpy as np
import numpy.typing as npt

from app.config import get_settings
from app.domain.transition.kernels.cosine import cosine_similarity_bulk
from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.domain.transition.weights import CAMELOT_HARMONIC_BASE
from app.shared.features import TrackFeatures


class HarmonicsComponent:
    name = "harmonics"
    default_weight = 0.15

    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        components: list[float] = []
        weights: list[float] = []

        floor = get_settings().transition.hard_reject_key_confidence_floor
        if (
            from_t.key_code is not None
            and to_t.key_code is not None
            and _key_reliable(from_t, floor)
            and _key_reliable(to_t, floor)
        ):
            from app.domain.camelot.wheel import camelot_distance

            dist = camelot_distance(from_t.key_code, to_t.key_code)
            base = CAMELOT_HARMONIC_BASE.get(dist, 0.0)
            if from_t.hnr_db is not None and to_t.hnr_db is not None:
                avg_hnr = (from_t.hnr_db + to_t.hnr_db) / 2
                hnr_factor = max(0.5, min(1.0, (avg_hnr + 30) / 30))
                base *= hnr_factor
            components.append(base)
            weights.append(0.40)
        else:
            components.append(0.5)
            weights.append(0.40)

        if from_t.tonnetz_vector and to_t.tonnetz_vector:
            components.append(_scalar_cosine(from_t.tonnetz_vector, to_t.tonnetz_vector))
            weights.append(0.20)

        if from_t.mfcc_vector and to_t.mfcc_vector:
            components.append(_scalar_cosine(from_t.mfcc_vector, to_t.mfcc_vector))
            weights.append(0.20)

        if from_t.spectral_contrast is not None and to_t.spectral_contrast is not None:
            diff = abs(from_t.spectral_contrast - to_t.spectral_contrast)
            components.append(max(0.0, 1.0 - diff / 15.0))
            weights.append(0.10)

        dissonance_penalty = 0.0
        if (
            from_t.dissonance_mean is not None
            and to_t.dissonance_mean is not None
            and from_t.dissonance_mean > 0.4
            and to_t.dissonance_mean > 0.4
        ):
            dissonance_penalty = 0.15

        base = _weighted_average(components, weights)
        return max(0.0, base - dissonance_penalty)

    def score_pairs(
        self, fa: FeatureArrays, ia: npt.NDArray[np.int64], ib: npt.NDArray[np.int64]
    ) -> npt.NDArray[np.float64]:
        from app.domain.transition.kernels.camelot_lookup import camelot_harmonic_score_bulk
        from app.domain.transition.scoring.bulk.arrays import key_reliable_mask

        key_a = fa.key_code[ia]
        key_b = fa.key_code[ib]
        key_present = (key_a >= 0) & (key_b >= 0)
        base_cam = camelot_harmonic_score_bulk(
            key_a, key_b, key_present, np.ones_like(key_present, dtype=np.bool_)
        )
        hnr_a = fa.hnr_db[ia]
        hnr_b = fa.hnr_db[ib]
        hnr_present = ~(np.isnan(hnr_a) | np.isnan(hnr_b))
        avg_hnr = (hnr_a + hnr_b) / 2.0
        hnr_factor = np.where(
            hnr_present, np.maximum(0.5, np.minimum(1.0, (avg_hnr + 30.0) / 30.0)), 1.0
        )
        reliable = key_reliable_mask(fa, ia) & key_reliable_mask(fa, ib)
        cam_term = np.where(key_present & reliable, base_cam * hnr_factor, 0.5)
        weight_cam = np.full_like(cam_term, 0.40)

        tonnetz_present = fa.tonnetz_present[ia] & fa.tonnetz_present[ib]
        tonnetz_cos = cosine_similarity_bulk(fa.tonnetz, ia, ib)
        tonnetz_term = np.where(tonnetz_present, tonnetz_cos, 0.0)
        weight_tonnetz = np.where(tonnetz_present, 0.20, 0.0)

        mfcc_present = fa.mfcc_present[ia] & fa.mfcc_present[ib]
        mfcc_cos = cosine_similarity_bulk(fa.mfcc, ia, ib)
        mfcc_term = np.where(mfcc_present, mfcc_cos, 0.0)
        weight_mfcc = np.where(mfcc_present, 0.20, 0.0)

        sc_a = fa.spectral_contrast[ia]
        sc_b = fa.spectral_contrast[ib]
        sc_present = ~(np.isnan(sc_a) | np.isnan(sc_b))
        sc_diff = np.abs(sc_a - sc_b)
        sc_term = np.where(sc_present, np.maximum(0.0, 1.0 - sc_diff / 15.0), 0.0)
        weight_sc = np.where(sc_present, 0.10, 0.0)

        numerator = (
            cam_term * weight_cam
            + tonnetz_term * weight_tonnetz
            + mfcc_term * weight_mfcc
            + sc_term * weight_sc
        )
        denominator = weight_cam + weight_tonnetz + weight_mfcc + weight_sc
        base = np.where(denominator > 0, numerator / denominator, 0.5)

        diss_a = fa.dissonance_mean[ia]
        diss_b = fa.dissonance_mean[ib]
        diss_present = ~(np.isnan(diss_a) | np.isnan(diss_b))
        both_dissonant = diss_present & (diss_a > 0.4) & (diss_b > 0.4)
        penalty = both_dissonant.astype(np.float64) * 0.15
        return np.maximum(0.0, base - penalty)


def _key_reliable(t: TrackFeatures, confidence_floor: float) -> bool:
    if t.atonality is True:
        return False
    return not (t.key_confidence is not None and t.key_confidence < confidence_floor)


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
