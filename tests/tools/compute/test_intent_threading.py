"""Audit iter 33 (T-31): ``transition_score_pool(intent=...)`` was
declared as a parameter on the tool signature but never passed to
``scorer.score(...)``. Same silent-no-op class as v1.2.12's
``sequence_optimize`` template fix.

Now intent is validated against the ``TransitionIntent`` enum
(maintain / ramp_up / cool_down / contrast) at the dispatcher
layer (Pydantic Literal) and threaded through to the scorer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.transition.intent import TransitionIntent
from app.tools.compute.score_pool import transition_score_pool


def _mock_score() -> MagicMock:
    score = MagicMock()
    score.overall = 0.5
    score.bpm = 0.5
    score.harmonics = 0.5
    score.energy = 0.5
    score.bass = 0.5
    score.drums = 0.5
    score.vocals = 0.5
    score.hard_reject = False
    return score


@pytest.mark.asyncio
async def test_intent_passed_to_scorer_when_set() -> None:
    """Capture the kwargs ``scorer.score`` receives and assert
    ``intent`` is the resolved ``TransitionIntent`` enum, not None."""
    captured: list[dict[str, object]] = []

    def _fake_score(*args: object, **kwargs: object) -> MagicMock:
        captured.append({"args": args, "kwargs": kwargs})
        return _mock_score()

    scorer = MagicMock()
    scorer.score = _fake_score

    feat = MagicMock(bpm=128.0)
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={146: feat, 147: feat})

    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    await transition_score_pool(
        track_ids=[146, 147],
        intent="ramp_up",
        uow=uow,
        scorer=scorer,
        ctx=ctx,
    )
    # Every call should carry intent=TransitionIntent.RAMP_UP.
    assert len(captured) == 2  # 146→147 and 147→146
    for call in captured:
        assert call["kwargs"].get("intent") == TransitionIntent.RAMP_UP


@pytest.mark.asyncio
async def test_intent_none_passes_none() -> None:
    captured: list[dict[str, object]] = []

    def _fake_score(*args: object, **kwargs: object) -> MagicMock:
        captured.append({"kwargs": kwargs})
        return _mock_score()

    scorer = MagicMock()
    scorer.score = _fake_score

    feat = MagicMock(bpm=128.0)
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={146: feat, 147: feat})

    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    await transition_score_pool(track_ids=[146, 147], uow=uow, scorer=scorer, ctx=ctx)
    for call in captured:
        assert call["kwargs"].get("intent") is None


@pytest.mark.asyncio
async def test_progress_reporting_is_headless_safe() -> None:
    scorer = MagicMock()
    scorer.score = MagicMock(return_value=_mock_score())

    feats = {tid: MagicMock(bpm=128.0) for tid in range(1, 12)}
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)

    ctx = MagicMock()
    ctx.report_progress = AsyncMock(side_effect=RuntimeError("session is not available"))

    result = await transition_score_pool(
        track_ids=list(feats),
        uow=uow,
        scorer=scorer,
        ctx=ctx,
    )

    assert result.track_ids == list(feats)
    assert len(result.pairs) == len(feats) * (len(feats) - 1)
