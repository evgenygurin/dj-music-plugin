from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt


def gauss_similarity(delta: float, sigma: float) -> float:
    return math.exp(-(delta**2) / (2.0 * sigma**2))


def gauss_similarity_bulk(delta: npt.NDArray[np.float64], sigma: float) -> npt.NDArray[np.float64]:
    return np.exp(-(delta**2) / (2.0 * sigma**2))
