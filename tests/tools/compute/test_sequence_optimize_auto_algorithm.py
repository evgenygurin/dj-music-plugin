"""``sequence_optimize(algorithm="auto")`` resolution rules.

The ``auto`` choice picks ``greedy`` for pools at or above
``_AUTO_GREEDY_THRESHOLD`` (200 tracks) where the GA's populate
+ generation loop blows past the wall-clock budget, and ``ga``
otherwise. Explicit ``"ga"`` / ``"greedy"`` always force the
choice — auto only fires when the caller passed nothing.

Acceptance:
* tool resolves ``"auto"`` to a concrete algorithm before calling
  ``optimizer_builder`` (the builder must never see ``"auto"``);
* the resolved name is what the response carries back so callers
  can observe what actually ran;
* explicit choices are never overridden.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.features import TrackFeatures
from app.tools.compute.sequence_optimize import sequence_optimize


def _features_for(track_ids: list[int]) -> dict[int, TrackFeatures]:
    return {tid: TrackFeatures(bpm=128.0 + i * 0.01) for i, tid in enumerate(track_ids)}


def _uow_with_features(feats: dict[int, TrackFeatures]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


def _capturing_builder(captured: dict[str, object]) -> MagicMock:
    """Optimizer factory that records the algorithm it was called with."""

    def fake_optimizer_builder(*, algorithm: str, scorer: object) -> object:
        captured["algorithm_passed_to_builder"] = algorithm

        result = MagicMock()
        result.track_order = list(range(captured.get("n", 0)))  # type: ignore[arg-type]
        result.quality_score = 0.5
        result.generations = 0

        def _optimize(**_kwargs: object) -> object:
            return result

        return MagicMock(optimize=_optimize)

    return fake_optimizer_builder  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_auto_picks_ga_below_threshold() -> None:
    """n < 200 with auto → GA."""
    track_ids = list(range(1, 51))
    feats = _features_for(track_ids)
    captured: dict[str, object] = {"n": len(track_ids)}

    out = await sequence_optimize(
        track_ids=track_ids,
        algorithm="auto",
        uow=_uow_with_features(feats),
        scorer=MagicMock(),
        optimizer_builder=_capturing_builder(captured),
    )
    assert captured["algorithm_passed_to_builder"] == "ga"
    assert out.algorithm == "ga"


@pytest.mark.asyncio
async def test_auto_picks_greedy_at_threshold() -> None:
    """n == 200 with auto → greedy (boundary inclusive)."""
    track_ids = list(range(1, 201))
    feats = _features_for(track_ids)
    captured: dict[str, object] = {"n": len(track_ids)}

    out = await sequence_optimize(
        track_ids=track_ids,
        algorithm="auto",
        uow=_uow_with_features(feats),
        scorer=MagicMock(),
        optimizer_builder=_capturing_builder(captured),
    )
    assert captured["algorithm_passed_to_builder"] == "greedy"
    assert out.algorithm == "greedy"


@pytest.mark.asyncio
async def test_explicit_ga_overrides_auto() -> None:
    """algorithm='ga' on a 300-track pool stays GA, even though auto would pick greedy."""
    track_ids = list(range(1, 301))
    feats = _features_for(track_ids)
    captured: dict[str, object] = {"n": len(track_ids)}

    out = await sequence_optimize(
        track_ids=track_ids,
        algorithm="ga",
        uow=_uow_with_features(feats),
        scorer=MagicMock(),
        optimizer_builder=_capturing_builder(captured),
    )
    assert captured["algorithm_passed_to_builder"] == "ga"
    assert out.algorithm == "ga"


@pytest.mark.asyncio
async def test_explicit_greedy_overrides_auto() -> None:
    """algorithm='greedy' on a 50-track pool stays greedy."""
    track_ids = list(range(1, 51))
    feats = _features_for(track_ids)
    captured: dict[str, object] = {"n": len(track_ids)}

    out = await sequence_optimize(
        track_ids=track_ids,
        algorithm="greedy",
        uow=_uow_with_features(feats),
        scorer=MagicMock(),
        optimizer_builder=_capturing_builder(captured),
    )
    assert captured["algorithm_passed_to_builder"] == "greedy"
    assert out.algorithm == "greedy"
