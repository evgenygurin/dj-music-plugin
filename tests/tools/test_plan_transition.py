from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_plan_transition_tool_uses_persisted_analysis_identities() -> None:
    from app.tools.compute.plan_transition import plan_transition

    service = MagicMock()
    service.execute = AsyncMock(return_value=MagicMock(value="planned", comparison=None))

    result = await plan_transition(
        1,
        2,
        "source-analysis",
        "target-analysis",
        bars=8,
        policy="best",
        service=service,
    )

    assert result["value"] == "planned"
    request = service.execute.await_args.args[0]
    assert request.source_analysis_identity == "source-analysis"
    assert request.target_analysis_identity == "target-analysis"
