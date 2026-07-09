from __future__ import annotations

import numpy as np
import numpy.typing as npt

from app.domain.transition.scoring.bulk.arrays import FeatureArrays
from app.shared.features import TrackFeatures


class VocalsComponent:
    name = "vocals"
    default_weight = 0.15

    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        components: list[float] = []
        weights: list[float] = []

        if from_t.spectral_centroid_hz is not None and to_t.spectral_centroid_hz is not None:
            max_c = max(from_t.spectral_centroid_hz, to_t.spectral_centroid_hz, 1.0)
            components.append(
                max(
                    0.0,
                    1.0 - abs(from_t.spectral_centroid_hz - to_t.spectral_centroid_hz) / max_c,
                )
            )
            weights.append(0.40)
        else:
            components.append(0.5)
            weights.append(0.40)

        if from_t.chroma_entropy is not None and to_t.chroma_entropy is not None:
            diff = abs(from_t.chroma_entropy - to_t.chroma_entropy)
            components.append(max(0.0, 1.0 - diff))
            weights.append(0.30)

        if from_t.pitch_salience_mean is not None and to_t.pitch_salience_mean is not None:
            diff = abs(from_t.pitch_salience_mean - to_t.pitch_salience_mean)
            components.append(max(0.0, 1.0 - diff / 0.5))
            weights.append(0.30)

        return _weighted_average(components, weights)

    def score_pairs(
        self, fa: FeatureArrays, ia: npt.NDArray[np.int64], ib: npt.NDArray[np.int64]
    ) -> npt.NDArray[np.float64]:
        cent_a = fa.spectral_centroid_hz[ia]
        cent_b = fa.spectral_centroid_hz[ib]
        cent_present = ~(np.isnan(cent_a) | np.isnan(cent_b))
        max_c = np.maximum(np.maximum(cent_a, cent_b), 1.0)
        cent_term = np.where(
            cent_present,
            np.maximum(0.0, 1.0 - np.abs(cent_a - cent_b) / max_c),
            0.5,
        )
        weight_cent = np.full_like(cent_term, 0.40)

        chroma_a = fa.chroma_entropy[ia]
        chroma_b = fa.chroma_entropy[ib]
        chroma_present = ~(np.isnan(chroma_a) | np.isnan(chroma_b))
        chroma_term = np.where(
            chroma_present, np.maximum(0.0, 1.0 - np.abs(chroma_a - chroma_b)), 0.0
        )
        weight_chroma = np.where(chroma_present, 0.30, 0.0)

        pitch_a = fa.pitch_salience_mean[ia]
        pitch_b = fa.pitch_salience_mean[ib]
        pitch_present = ~(np.isnan(pitch_a) | np.isnan(pitch_b))
        pitch_term = np.where(
            pitch_present, np.maximum(0.0, 1.0 - np.abs(pitch_a - pitch_b) / 0.5), 0.0
        )
        weight_pitch = np.where(pitch_present, 0.30, 0.0)

        numerator = (
            cent_term * weight_cent + chroma_term * weight_chroma + pitch_term * weight_pitch
        )
        denominator = weight_cent + weight_chroma + weight_pitch
        return np.where(denominator > 0, numerator / denominator, 0.5)


def _weighted_average(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.5
    total_w = sum(weights)
    if total_w == 0:
        return 0.5
    return sum(v * w for v, w in zip(values, weights, strict=False)) / total_w
