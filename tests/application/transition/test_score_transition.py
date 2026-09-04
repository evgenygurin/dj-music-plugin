"""Application boundary tests for pairwise transition scoring."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.transition.score import ScoreTransition


@pytest.mark.asyncio
async def test_score_transition_loads_both_features_and_delegates() -> None:
    catalog = MagicMock()
    catalog.features = AsyncMock(return_value={1: "source", 2: "target"})
    scorer = MagicMock()
    expected = object()
    scorer.score.return_value = expected

    result = await ScoreTransition(catalog, scorer).execute(1, 2, weights="weights")

    catalog.features.assert_awaited_once_with([1, 2])
    scorer.score.assert_called_once_with("source", "target", weights="weights")
    assert result is expected


@pytest.mark.asyncio
async def test_score_transition_reports_missing_features() -> None:
    catalog = MagicMock()
    catalog.features = AsyncMock(return_value={1: "source"})
    scorer = MagicMock()

    with pytest.raises(ValueError, match="missing scoring features"):
        await ScoreTransition(catalog, scorer).execute(1, 2)

    scorer.score.assert_not_called()
