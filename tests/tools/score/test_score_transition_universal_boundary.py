"""Universal application-boundary tests for score_transition."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.scoring import ScoringWeights
from app.tools.score.score_harmonic import ScoreTransitionResult, score_transition


@pytest.mark.asyncio
async def test_tool_delegates_pair_scoring_to_application_use_case() -> None:
    use_case = MagicMock()
    expected = ScoreTransitionResult(
        a_id=1,
        b_id=2,
        S_harmony=0.9,
        S_rhythmic=0.8,
        S_timbral=0.7,
        S_energy=0.6,
        S_structure=0.5,
        overall=0.7,
        weights=ScoringWeights(),
    )
    use_case.execute = AsyncMock(return_value=expected)

    result = await score_transition(1, 2, generator=use_case)

    use_case.execute.assert_awaited_once_with(1, 2, weights=None)
    assert result == expected
