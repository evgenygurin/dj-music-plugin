"""Pure math helpers: bpm_distance / cosine_similarity / correlation."""

from __future__ import annotations

import math

from app.v2.domain.transition.math_helpers import (
    bpm_distance,
    correlation,
    cosine_similarity,
)


def test_bpm_distance_zero_identity() -> None:
    assert bpm_distance(128.0, 128.0) == 0.0


def test_bpm_distance_half_tempo_folds_to_zero() -> None:
    assert bpm_distance(64.0, 128.0) == 0.0


def test_bpm_distance_normal_gap() -> None:
    assert bpm_distance(128.0, 130.0) == 2.0


def test_cosine_similarity_identity_one() -> None:
    assert math.isclose(cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)


def test_cosine_similarity_orthogonal_half() -> None:
    # Normalised to [0, 1]: orthogonal -> 0.5, anti-parallel -> 0.
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.5, abs_tol=1e-9)


def test_correlation_perfect_positive() -> None:
    assert math.isclose(correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]), 1.0, abs_tol=1e-9)
