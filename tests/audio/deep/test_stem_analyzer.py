from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.audio.deep.stem_analyzer import analyze_stems


@pytest.mark.asyncio
async def test_analyze_stems_calls_pipeline_5_times() -> None:
    # 5-stem contract from demucs_runner (harmonic = other; percussion = drums split)
    stem_paths = {
        "vocals": Path("/tmp/vocals.wav"),
        "drums": Path("/tmp/drums.wav"),
        "bass": Path("/tmp/bass.wav"),
        "harmonic": Path("/tmp/harmonic.wav"),
        "percussion": Path("/tmp/percussion.wav"),
    }
    original = Path("/tmp/original.wav")

    pipeline_results = {"bpm": 130.0, "integrated_lufs": -8.5, "mood": "peak_time"}
    mock_pipeline = AsyncMock()
    mock_pipeline.analyze = AsyncMock(return_value=MagicMock(features=pipeline_results))

    with patch(
        "app.audio.deep.stem_analyzer._make_pipeline",
        return_value=mock_pipeline,
    ):
        result = await analyze_stems(stem_paths, original)

    assert mock_pipeline.analyze.call_count == 6  # 5 stems + original
    assert result["original"] == pipeline_results
    assert result["vocals"] == pipeline_results
    assert result["drums"] == pipeline_results
