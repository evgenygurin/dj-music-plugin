from __future__ import annotations

import numpy as np
import numpy.typing as npt

from app.domain.transition.kernels.gauss import gauss_similarity


def bpm_gauss(bpm_a: float, bpm_b: float, sigma: float = 2.0) -> float:
    """BPM compatibility score via gaussian kernel on bpm_distance."""
    d = bpm_distance(bpm_a, bpm_b)
    return gauss_similarity(d, sigma)


def bpm_distance(bpm_a: float, bpm_b: float) -> float:
    """Minimum BPM distance considering double/half-time."""
    if bpm_a <= 0 or bpm_b <= 0:
        return 999.0
    d = abs(bpm_a - bpm_b)
    d2 = abs(bpm_a - bpm_b / 2)
    dh = abs(bpm_a - bpm_b * 2)
    return float(min(d, d2, dh))


def bpm_distance_bulk(
    bpm_a: npt.NDArray[np.float64],
    bpm_b: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Vectorized bpm_distance."""
    d = np.abs(bpm_a - bpm_b)
    d2 = np.abs(bpm_a - bpm_b / 2.0)
    dh = np.abs(bpm_a - bpm_b * 2.0)
    return np.minimum(np.minimum(d, d2), dh)
