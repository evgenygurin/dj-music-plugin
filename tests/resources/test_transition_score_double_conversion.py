"""Regression: /score must not re-run ``TrackFeatures.from_db`` on TrackFeatures.

``_load_features_pair`` returns ``TrackFeatures`` dataclasses (that is what
``get_scoring_features_batch`` produces), but the resource then called
``TrackFeatures.from_db(feat)`` a second time. ``from_db`` rebuilds
``energy_bands`` from the ``energy_sub`` / ``energy_low`` / ... DB columns,
which do not exist on the dataclass — so the double conversion silently
dropped ``energy_bands`` (and the batch-computed mix-in/mix-out points),
zeroing the bass-band term of ``S_bass``. The same pair scored differently
via ``transition_score_pool`` (bulk path, correct) and
``local://transition/{a}/{b}/score`` (production pair 3156→3166:
bass 0.670 vs 0.593, 2026-07-03).

Prior tests missed it because they mock features with ``MagicMock``, which
tolerates a second ``from_db`` pass. This test uses real ``TrackFeatures``.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.transition.scorer import TransitionScorer
from app.resources.transition import transition_explain, transition_score
from app.shared.features import TrackFeatures


def _real_features(*, key_code: int, atonality: bool, bands: list[float]) -> TrackFeatures:
    return TrackFeatures(
        bpm=128.0,
        bpm_confidence=1.0,
        bpm_stability=0.9,
        variable_tempo=False,
        key_code=key_code,
        key_confidence=1.0,
        atonality=atonality,
        integrated_lufs=-12.0,
        spectral_centroid_hz=2000.0,
        energy_mean=0.4,
        onset_rate=2.0,
        kick_prominence=0.8,
        hnr_db=-10.0,
        chroma_entropy=0.97,
        energy_bands=bands,
    )


def _uow_with(fa: TrackFeatures, fb: TrackFeatures) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={1: fa, 2: fb})
    return uow


@pytest.mark.asyncio
async def test_score_resource_matches_direct_scorer_with_energy_bands() -> None:
    fa = _real_features(key_code=5, atonality=False, bands=[0.41, 0.53, 0.04, 0.01, 0.006, 0.004])
    fb = _real_features(key_code=20, atonality=True, bands=[0.30, 0.62, 0.03, 0.02, 0.011, 0.009])

    expected = TransitionScorer().score(fa, fb)
    payload = json.loads(await transition_score(from_id=1, to_id=2, uow=_uow_with(fa, fb)))

    assert payload["components"]["bass"] == pytest.approx(expected.bass), (
        "resource bass diverged from direct scorer — energy_bands lost in transit?"
    )
    assert payload["overall"] == pytest.approx(expected.overall)


@pytest.mark.asyncio
async def test_explain_resource_matches_direct_scorer_with_energy_bands() -> None:
    fa = _real_features(key_code=5, atonality=False, bands=[0.41, 0.53, 0.04, 0.01, 0.006, 0.004])
    fb = _real_features(key_code=20, atonality=True, bands=[0.30, 0.62, 0.03, 0.02, 0.011, 0.009])

    expected = TransitionScorer().score(fa, fb)
    payload = json.loads(await transition_explain(from_id=1, to_id=2, uow=_uow_with(fa, fb)))

    assert payload["overall"] == pytest.approx(expected.overall)
