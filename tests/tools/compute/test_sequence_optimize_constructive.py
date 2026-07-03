"""Constructive mode for ``sequence_optimize``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.errors import ValidationError
from app.shared.features import TrackFeatures
from app.tools.compute.sequence_optimize import sequence_optimize


def _uow_with_features(feats: dict[int, TrackFeatures]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


@pytest.mark.asyncio
async def test_constructive_requires_template() -> None:
    with pytest.raises(ValidationError, match="requires a valid template"):
        await sequence_optimize(
            track_ids=[1, 2, 3],
            algorithm="constructive",
            uow=_uow_with_features(
                {
                    1: TrackFeatures(bpm=130.0),
                    2: TrackFeatures(bpm=132.0),
                    3: TrackFeatures(bpm=134.0),
                }
            ),
            scorer=MagicMock(),
            optimizer_builder=MagicMock(),
        )


@pytest.mark.asyncio
async def test_constructive_passes_through_and_returns_subset() -> None:
    feats = {
        1: TrackFeatures(bpm=130.0, mood="minimal"),
        2: TrackFeatures(bpm=134.0, mood="hypnotic"),
        3: TrackFeatures(bpm=138.0, mood="driving"),
        4: TrackFeatures(bpm=145.0, mood="raw"),
    }
    captured: dict[str, object] = {}

    def fake_optimizer_builder(*, algorithm: str, scorer: object) -> object:
        captured["algorithm"] = algorithm

        result = MagicMock()
        result.track_order = [1, 2, 3]
        result.quality_score = 0.91
        result.generations = 3

        def _optimize(**kwargs: object) -> object:
            captured["template"] = kwargs["template"]
            return result

        return MagicMock(optimize=_optimize)

    out = await sequence_optimize(
        track_ids=[1, 2, 3, 4],
        algorithm="constructive",
        template="roller_90",
        uow=_uow_with_features(feats),
        scorer=MagicMock(),
        optimizer_builder=fake_optimizer_builder,
    )

    assert captured["algorithm"] == "constructive"
    assert captured["template"] is not None
    assert out.track_order == [1, 2, 3]
    assert out.algorithm == "constructive"
