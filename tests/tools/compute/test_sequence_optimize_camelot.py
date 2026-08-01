"""``sequence_optimize(camelot_mode=...)`` must forward ``soft_camelot`` to the optimizer builder."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.features import TrackFeatures
from app.tools.compute.sequence_optimize import sequence_optimize


def _uow_with_features(feats: dict[int, TrackFeatures]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


def _capturing_builder(captured: dict[str, object]) -> object:
    def fake_optimizer_builder(
        *, algorithm: str, scorer: object, soft_camelot: bool = False
    ) -> object:
        captured["soft_camelot"] = soft_camelot
        result = MagicMock()
        result.track_order = [1, 2]
        result.quality_score = 0.5
        result.generations = 0
        return MagicMock(optimize=lambda **kw: result)

    return fake_optimizer_builder


@pytest.mark.asyncio
async def test_camelot_mode_soft_forwards_true() -> None:
    captured: dict[str, object] = {}
    out = await sequence_optimize(
        track_ids=[1, 2],
        camelot_mode="soft",
        uow=_uow_with_features({1: TrackFeatures(bpm=130.0), 2: TrackFeatures(bpm=132.0)}),
        scorer=MagicMock(),
        optimizer_builder=_capturing_builder(captured),
    )
    assert captured["soft_camelot"] is True
    assert out.track_order == [1, 2]


@pytest.mark.asyncio
async def test_camelot_mode_default_strict() -> None:
    captured: dict[str, object] = {}
    await sequence_optimize(
        track_ids=[1, 2],
        uow=_uow_with_features({1: TrackFeatures(bpm=130.0), 2: TrackFeatures(bpm=132.0)}),
        scorer=MagicMock(),
        optimizer_builder=_capturing_builder(captured),
    )
    assert captured["soft_camelot"] is False
