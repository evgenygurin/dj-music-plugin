from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.handlers.deep_analysis import handle_deep_analyze_track


@pytest.mark.asyncio
async def test_handler_returns_job_id() -> None:
    uow = MagicMock()
    uow.feature_extraction_runs = MagicMock()
    uow.feature_extraction_runs.create = AsyncMock(return_value=MagicMock(id=42))

    with (
        patch(
            "app.handlers.deep_analysis.L6AnalysisOrchestrator",
            return_value=MagicMock(run=AsyncMock()),
        ),
        patch(
            "app.handlers.deep_analysis.SupabaseStorageClient",
            return_value=MagicMock(),
        ),
    ):
        result = await handle_deep_analyze_track(track_id=1, uow=uow)

    assert result["job_id"] is not None
    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_handler_refuses_without_library_item() -> None:
    uow = MagicMock()
    uow.audio_files = MagicMock()
    uow.audio_files.get_by_track_id = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="library_item"):
        await handle_deep_analyze_track(track_id=1, uow=uow, check_prereqs=True)
