"""compute_fitness on a small synthetic set."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.domain.optimization.fitness import compute_fitness, transition_quality
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.scorer import TransitionScorer
from app.domain.transition.section_context import SectionPairClass
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures


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


def test_transition_quality_passes_shared_pair_context_to_scorer() -> None:
    scorer = MagicMock()
    scorer.score.return_value = MagicMock(overall=0.75, hard_reject=False)
    tracks = [
        TrackFeatures(
            integrated_lufs=-12.0,
            mix_out_section_type=int(SectionType.OUTRO),
        ),
        TrackFeatures(
            integrated_lufs=-10.5,
            mix_in_section_type=int(SectionType.INTRO),
        ),
    ]

    result = transition_quality(scorer, tracks, [1, 2], {1: 0, 2: 1})

    assert result == pytest.approx(0.75)
    call = scorer.score.call_args
    assert call.kwargs["intent"] == TransitionIntent.RAMP_UP
    assert call.kwargs["section_context"].section_pair_class == SectionPairClass.DRUM_ONLY
