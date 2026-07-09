from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.audio.deep.stem_analyzer import analyze_stems


@pytest.mark.asyncio
async def test_analyze_stems_calls_pipeline_5_times() -> None:
    uow = MagicMock()
    stem_paths = {
        "vocals": Path("/tmp/vocals.wav"),
        "drums": Path("/tmp/drums.wav"),
        "bass": Path("/tmp/bass.wav"),
        "other": Path("/tmp/other.wav"),
    }
    original = Path("/tmp/original.wav")

    pipeline_results = {"bpm": 130.0, "integrated_lufs": -8.5, "mood": "peak_time"}

    with patch(
        "app.audio.deep.stem_analyzer.run_pipeline",
        new_callable=AsyncMock,
        return_value=pipeline_results,
    ) as mock_pipeline:
        result = await analyze_stems(uow, 1, stem_paths, original)

    assert mock_pipeline.call_count == 5
    assert result["original"] == pipeline_results
    assert result["vocals"] == pipeline_results
    assert "drums" in result
    assert "bass" in result
    assert "other" in result
