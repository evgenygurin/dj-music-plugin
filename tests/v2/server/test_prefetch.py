"""SpeculativePrefetch — warms transition scoring + L3 analysis for top candidates."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.v2.config import get_settings, reset_settings_cache
from app.v2.server.prefetch import SpeculativePrefetch


@pytest.fixture(autouse=True)
def _isolate_settings() -> None:
    reset_settings_cache()


@pytest.mark.asyncio
async def test_prefetch_respects_top_n_cap() -> None:
    uow = MagicMock()
    uow.track_features.get_analysis_level = AsyncMock(return_value=3)
    uow.tracks.get_provider_id = AsyncMock(return_value="yandex-id")
    scorer = AsyncMock()

    pre = SpeculativePrefetch(uow=uow, scorer=scorer, settings=get_settings().discovery)
    await pre.warm(from_track_id=1, candidate_ids=[2, 3, 4, 5, 6, 7, 8, 9, 10, 11])

    # Default prefetch_top_n = 3 — scorer called at most 3 times.
    assert scorer.call_count <= 3


@pytest.mark.asyncio
async def test_prefetch_skips_when_top_n_is_zero() -> None:
    uow = MagicMock()
    scorer = AsyncMock()

    settings = get_settings().discovery.model_copy(update={"prefetch_top_n": 0})
    pre = SpeculativePrefetch(uow=uow, scorer=scorer, settings=settings)
    await pre.warm(from_track_id=1, candidate_ids=[2, 3, 4])

    scorer.assert_not_called()


@pytest.mark.asyncio
async def test_prefetch_triggers_l3_when_below_threshold() -> None:
    uow = MagicMock()
    analyze_handler = AsyncMock()
    uow.track_features.get_analysis_level = AsyncMock(side_effect=[2, 3])

    pre = SpeculativePrefetch(
        uow=uow,
        scorer=AsyncMock(),
        settings=get_settings().discovery,
        analyze_handler=analyze_handler,
    )
    await pre.warm(from_track_id=1, candidate_ids=[2, 3])

    analyze_handler.assert_awaited_once()
    args, kwargs = analyze_handler.await_args
    assert kwargs.get("track_ids") == [2] or (args and args[0] == [2])


@pytest.mark.asyncio
async def test_prefetch_errors_are_swallowed_not_propagated() -> None:
    uow = MagicMock()
    uow.track_features.get_analysis_level = AsyncMock(side_effect=RuntimeError("boom"))

    pre = SpeculativePrefetch(uow=uow, scorer=AsyncMock(), settings=get_settings().discovery)

    # Must NOT raise — prefetch is best-effort background work.
    await pre.warm(from_track_id=1, candidate_ids=[2, 3])
