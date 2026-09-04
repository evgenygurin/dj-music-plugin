"""Universal application-boundary tests for candidate discovery."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.transition.candidates import CandidateSummary
from app.schemas.tool_responses import TransitionCandidatesResult
from app.tools.compute.transition_candidates import get_transition_candidates


@pytest.mark.asyncio
async def test_tool_delegates_candidate_discovery_to_application_use_case() -> None:
    use_case = MagicMock()
    use_case.execute = AsyncMock(
        return_value=(CandidateSummary(track_id=2, overall=0.91, title="Other"),)
    )
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()

    result = await get_transition_candidates(
        track_id=1,
        top_k=5,
        min_score=0.3,
        generator=use_case,
        ctx=ctx,
    )

    use_case.execute.assert_awaited_once_with(1, top_k=5, min_score=0.3)
    assert isinstance(result, TransitionCandidatesResult)
    assert result.from_track_id == 1
    assert result.candidates[0].track_id == 2
    assert result.candidates[0].title == "Other"


@pytest.mark.asyncio
async def test_tool_preserves_missing_source_contract_from_use_case() -> None:
    use_case = MagicMock()
    use_case.execute = AsyncMock(return_value=())
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()

    result = await get_transition_candidates(track_id=7, generator=use_case, ctx=ctx)

    assert result.from_track_id == 7
    assert result.missing_features is True
    assert result.candidates == []
