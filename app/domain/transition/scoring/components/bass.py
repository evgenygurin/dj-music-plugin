from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

from app.config import get_settings
from app.domain.transition.kernels.bpm_distance import bpm_distance, bpm_distance_bulk
from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.domain.transition.weights import CAMELOT_BASS_BASE
from app.shared.features import TrackFeatures


class BassComponent:
    name = "bass"
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
            components.append(CAMELOT_BASS_BASE.get(dist, 0.0))
            weights.append(0.65)
        else:
            components.append(0.5)
            weights.append(0.65)

        if from_t.energy_bands and to_t.energy_bands:
            bass_a = from_t.energy_bands[0] + from_t.energy_bands[1]
            bass_b = to_t.energy_bands[0] + to_t.energy_bands[1]
            max_bass = max(bass_a, bass_b, 1e-6)
            components.append(max(0.0, 1.0 - abs(bass_a - bass_b) / max_bass))
            weights.append(0.20)

        if from_t.bpm is not None and to_t.bpm is not None:
            delta = bpm_distance(from_t.bpm, to_t.bpm)
            components.append(math.exp(-(delta**2) / 18.0))
            weights.append(0.15)

        return _weighted_average(components, weights)

    def score_pairs(
        self, fa: FeatureArrays, ia: npt.NDArray[np.int64], ib: npt.NDArray[np.int64]
    ) -> npt.NDArray[np.float64]:
        from app.domain.transition.kernels.camelot_lookup import camelot_bass_score_bulk
        from app.domain.transition.scoring.bulk.arrays import key_reliable_mask

        key_a = fa.key_code[ia]
        key_b = fa.key_code[ib]
        key_present = (key_a >= 0) & (key_b >= 0)
        reliable = key_reliable_mask(fa, ia) & key_reliable_mask(fa, ib)
        cam_term = camelot_bass_score_bulk(key_a, key_b, key_present, reliable)
        weight_cam = np.full_like(cam_term, 0.65)

        eb_present = fa.energy_bands_present[ia] & fa.energy_bands_present[ib]
        bass_a = fa.energy_bands[ia, 0] + fa.energy_bands[ia, 1]
        bass_b = fa.energy_bands[ib, 0] + fa.energy_bands[ib, 1]
        max_bass = np.maximum(np.maximum(bass_a, bass_b), 1e-6)
        bass_band_term = np.where(
            eb_present,
            np.maximum(0.0, 1.0 - np.abs(bass_a - bass_b) / max_bass),
            0.0,
        )
        weight_bb = np.where(eb_present, 0.20, 0.0)

        bpm_a = fa.bpm[ia]
        bpm_b = fa.bpm[ib]
        bpm_present = ~(np.isnan(bpm_a) | np.isnan(bpm_b))
        delta = bpm_distance_bulk(bpm_a, bpm_b)
        bpm_score = np.exp(-(delta**2) / 18.0)
        bpm_term = np.where(bpm_present, bpm_score, 0.0)
        weight_bpm = np.where(bpm_present, 0.15, 0.0)

        numerator = cam_term * weight_cam + bass_band_term * weight_bb + bpm_term * weight_bpm
        denominator = weight_cam + weight_bb + weight_bpm
        return np.where(denominator > 0, numerator / denominator, 0.5)


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
