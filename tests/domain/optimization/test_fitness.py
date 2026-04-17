"""compute_fitness on a small synthetic set."""

from __future__ import annotations

import pytest

from app.domain.optimization.fitness import compute_fitness
from app.domain.transition.features import TrackFeatures
from app.domain.transition.scorer import TransitionScorer


def _features_map() -> dict[int, TrackFeatures]:
    base = dict(
        integrated_lufs=-8.0,
        energy_mean=0.3,
        spectral_centroid_hz=3000.0,
        onset_rate=5.0,
        kick_prominence=0.5,
        hnr_db=10.0,
        chroma_entropy=0.6,
    )
    return {
        101: TrackFeatures(bpm=124.0, key_code=5, **base),
        102: TrackFeatures(bpm=126.0, key_code=7, **base),
        103: TrackFeatures(bpm=128.0, key_code=5, **base),
    }


def _as_lists(fmap: dict[int, TrackFeatures]) -> tuple[list[TrackFeatures], list[int]]:
    ids = list(fmap.keys())
    return [fmap[i] for i in ids], ids


def test_fitness_in_unit_interval() -> None:
    fmap = _features_map()
    tracks, ids = _as_lists(fmap)
    idx_map = {tid: i for i, tid in enumerate(ids)}
    score = compute_fitness(TransitionScorer(), tracks, ids, idx_map)
    assert 0.0 <= score <= 1.0


def test_fitness_deterministic() -> None:
    fmap = _features_map()
    tracks, ids = _as_lists(fmap)
    idx_map = {tid: i for i, tid in enumerate(ids)}
    a = compute_fitness(TransitionScorer(), tracks, ids, idx_map)
    b = compute_fitness(TransitionScorer(), tracks, ids, idx_map)
    assert a == pytest.approx(b)
