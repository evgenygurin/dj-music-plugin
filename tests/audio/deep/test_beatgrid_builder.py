from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.audio.deep.beatgrid_builder import build_beatgrid


@pytest.mark.asyncio
async def test_build_beatgrid_registers_in_db() -> None:
    uow = MagicMock()
    uow.audio_files = MagicMock()
    uow.audio_files.register_beatgrid = AsyncMock()
    uow.audio_files.get_for_track = AsyncMock(return_value=MagicMock(id=42))

    with patch(
        "app.audio.deep.beatgrid_builder.compute_kick_phase",
        return_value=(0.0, 0.05),
    ), patch(
        "app.audio.deep.beatgrid_builder.refine_phase",
        return_value=(0.01, 0.02),
    ), patch(
        "app.audio.deep.beatgrid_builder._get_bpm_from_path",
        return_value=130.0,
    ):
        result = await build_beatgrid(uow, track_id=1, audio_path=Path("/tmp/test.mp3"))

    uow.audio_files.register_beatgrid.assert_called_once()
    assert result.bpm == 130.0
    assert result.phase_ms is not None
