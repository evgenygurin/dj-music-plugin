from __future__ import annotations

import numpy as np
import numpy.typing as npt

from app.domain.camelot.wheel import camelot_distance
from app.domain.transition.weights import CAMELOT_BASS_BASE, CAMELOT_HARMONIC_BASE


def key_distance(key_a: int, key_b: int) -> int:
    """Raw Camelot distance between two keys (0-7)."""
    return camelot_distance(key_a, key_b)


def camelot_harmonic_score(key_a: int | None, key_b: int | None) -> float:
    if key_a is None or key_b is None:
        return 0.5
    dist = camelot_distance(key_a, key_b)
    return float(CAMELOT_HARMONIC_BASE.get(dist, 0.0))


def camelot_harmonic_score_bulk(
    key_a: npt.NDArray[np.int64],
    key_b: npt.NDArray[np.int64],
    key_present: npt.NDArray[np.bool_],
    reliable: npt.NDArray[np.bool_],
) -> npt.NDArray[np.float64]:
    base_lookup = np.array([CAMELOT_HARMONIC_BASE.get(d, 0.0) for d in range(8)], dtype=np.float64)
    pos_a = np.floor_divide(key_a, 2)
    mode_a = np.fmod(key_a, 2)
    pos_b = np.floor_divide(key_b, 2)
    mode_b = np.fmod(key_b, 2)
    raw_diff = np.abs(pos_a - pos_b)
    wheel_dist = np.minimum(raw_diff, 12 - raw_diff)
    mode_penalty = np.where(mode_a != mode_b, 1, 0)
    dist = (wheel_dist + mode_penalty).astype(np.int64)
    scores = base_lookup[np.clip(dist, 0, 7)]
    return np.where(key_present & reliable, scores, 0.5)


def camelot_bass_score(key_a: int | None, key_b: int | None) -> float:
    if key_a is None or key_b is None:
        return 0.5
    dist = camelot_distance(key_a, key_b)
    return float(CAMELOT_BASS_BASE.get(dist, 0.0))


def camelot_bass_score_bulk(
    key_a: npt.NDArray[np.int64],
    key_b: npt.NDArray[np.int64],
    key_present: npt.NDArray[np.bool_],
    reliable: npt.NDArray[np.bool_],
) -> npt.NDArray[np.float64]:
    base_lookup = np.array([CAMELOT_BASS_BASE.get(d, 0.0) for d in range(8)], dtype=np.float64)
    pos_a = np.floor_divide(key_a, 2)
    mode_a = np.fmod(key_a, 2)
    pos_b = np.floor_divide(key_b, 2)
    mode_b = np.fmod(key_b, 2)
    raw_diff = np.abs(pos_a - pos_b)
    wheel_dist = np.minimum(raw_diff, 12 - raw_diff)
    mode_penalty = np.where(mode_a != mode_b, 1, 0)
    dist = (wheel_dist + mode_penalty).astype(np.int64)
    scores = base_lookup[np.clip(dist, 0, 7)]
    return np.where(key_present & reliable, scores, 0.5)
