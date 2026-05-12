"""Audit iter 57 (T-55): ``local://transition/{a}/{b}/score`` and
``/explain`` recomputed via ``TransitionScorer`` regardless of
whether ``a == b``, returning a synthetic 0.93 self-similarity row
for a track-against-itself query.

Live confirmation:

    /transition/146/146/score
    -> {"overall":0.93, "components":{"bpm":0.78,"harmonic":1.0, ...}}
    /transition/146/146/explain
    -> {"narrative":"BPM: 128.09 -> 128.09 ..."}

This mirrors the T-52 hole on the write path (entity_create
transition with from==to) which v1.2.51-52 already closed. The
read paths now reject the same input up front via the shared
``_load_features_pair`` helper.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.transition import transition_explain, transition_score
from app.shared.errors import ValidationError


@pytest.mark.asyncio
async def test_score_rejects_same_track() -> None:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    with pytest.raises(ValidationError, match=r"undefined for a track against itself"):
        await transition_score(from_id=146, to_id=146, uow=uow)


@pytest.mark.asyncio
async def test_explain_rejects_same_track() -> None:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    with pytest.raises(ValidationError, match=r"undefined for a track against itself"):
        await transition_explain(from_id=146, to_id=146, uow=uow)


@pytest.mark.asyncio
async def test_score_distinct_pair_still_runs_features_load() -> None:
    """Sanity: distinct ids still hit the ``track_features`` lookup.

    The same-track guard fires BEFORE the features lookup, so the mock
    needs no setup for it. With distinct ids, the lookup runs (and
    raises NotFoundError because we don't seed features). That's the
    expected contract — the guard does not short-circuit valid input.
    """
    from app.shared.errors import NotFoundError

    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    with pytest.raises(NotFoundError, match=r"track_features"):
        await transition_score(from_id=146, to_id=147, uow=uow)


@pytest.mark.asyncio
async def test_missing_features_message_pinpoints_the_actual_id() -> None:
    """Regression: the message used to say ``"track_features not found:
    '9999 or 2'"`` (literally "X or Y") even when only one side was
    missing, leaving callers guessing. Now it reports the missing id
    directly.
    """
    from app.shared.errors import NotFoundError

    feat = MagicMock()
    uow = MagicMock()
    uow.track_features = MagicMock()
    # Only ``2`` has features; ``9999`` is the one truly missing.
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={2: feat})
    with pytest.raises(NotFoundError) as info:
        await transition_score(from_id=9999, to_id=2, uow=uow)
    msg = str(info.value)
    assert "9999" in msg
    assert " or " not in msg, f"old ambiguous 'X or Y' phrasing leaked: {msg!r}"


@pytest.mark.asyncio
async def test_missing_features_message_when_both_sides_missing() -> None:
    """When both sides are missing the message uses ``both X and Y``
    instead of the ambiguous ``X or Y`` (so the caller knows that
    seeding either side alone won't be enough)."""
    from app.shared.errors import NotFoundError

    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    with pytest.raises(NotFoundError) as info:
        await transition_score(from_id=8888, to_id=9999, uow=uow)
    msg = str(info.value)
    assert "8888" in msg and "9999" in msg
    assert "both" in msg
