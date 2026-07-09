from __future__ import annotations

import numpy as np
import numpy.typing as npt

from app.domain.transition.neural_mix import (
    TRANSITION_ENERGY_BIAS,
    TRANSITION_STEM_WEIGHTS,
    NeuralMixStem,
    NeuralMixTransition,
)

FloatArr = npt.NDArray[np.float64]


def _stem_weight_matrix() -> tuple[FloatArr, FloatArr, list[NeuralMixTransition]]:
    transitions = list(NeuralMixTransition)
    stems_order: list[NeuralMixStem] = [
        NeuralMixStem.DRUMS,
        NeuralMixStem.BASS,
        NeuralMixStem.HARMONICS,
        NeuralMixStem.VOCALS,
    ]
    stem_w = np.zeros((len(transitions), 4), dtype=np.float64)
    bias = np.zeros(len(transitions), dtype=np.float64)
    for i, t in enumerate(transitions):
        for j, s in enumerate(stems_order):
            stem_w[i, j] = TRANSITION_STEM_WEIGHTS[t][s]
        bias[i] = TRANSITION_ENERGY_BIAS[t]
    return stem_w, bias, transitions


_STEM_W_MATRIX, _BIAS_VEC, _TRANSITION_ORDER = _stem_weight_matrix()


def get_stem_weight_matrix() -> FloatArr:
    return _STEM_W_MATRIX


def get_bias_vec() -> FloatArr:
    return _BIAS_VEC


def get_transition_order() -> list[NeuralMixTransition]:
    return list(_TRANSITION_ORDER)


def energy_bias_modifier_bulk(
    energy_delta: FloatArr,
) -> FloatArr:
    delta = np.where(np.isnan(energy_delta), 0.0, energy_delta)
    normalised = np.clip(delta / 4.0, -1.0, 1.0)
    bias = _BIAS_VEC
    alignment = normalised[:, None] * bias[None, :]
    pos = np.maximum(0.0, alignment)
    neg = np.maximum(0.0, -alignment)
    bias_zero = bias == 0.0
    modifier = 1.0 + 0.15 * pos - 0.30 * neg
    return np.where(bias_zero[None, :], 1.0, modifier)
