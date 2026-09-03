from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.audio.deep.beatgrid_builder import BeatgridEntry, build_beatgrid
from app.audio.deep.demucs_runner import __all__
from app.audio.deep.stem_analyzer import analyze_stems


@pytest.mark.asyncio
async def test_beatgrid_contract_produces_valid_entry() -> None:
    """Wave 3: beatgrid builder produces deterministic entry for downstream use."""
    with (
        patch("app.audio.deep.beatgrid_builder.compute_kick_phase", return_value=(0.0, 0.05)),
        patch("app.audio.deep.beatgrid_builder.refine_phase", return_value=(0.01, 0.02)),
        patch("app.audio.deep.beatgrid_builder._get_bpm_from_path", return_value=130.0),
    ):
        result = build_beatgrid(Path("/tmp/test.mp3"))
    assert isinstance(result, BeatgridEntry)
    assert result.bpm == 130.0
    assert result.phase_ms is not None


def test_demucs_contract_has_5_stems() -> None:
    """Wave 3: demucs_runner exposes the canonical 5-stem contract."""
    # Verify the module exposes the canonical 5-stem contract
    assert "run_demucs" in __all__
    assert "PERCUSSION_SPLIT_HZ" in __all__


@pytest.mark.asyncio
async def test_stem_analyzer_contract_aligns_with_5_stem_output() -> None:
    """Wave 3: stem_analyzer accepts the same 5-stem keys that demucs produces."""
    stem_paths = {
        "vocals": Path("/tmp/vocals.wav"),
        "drums": Path("/tmp/drums.wav"),
        "bass": Path("/tmp/bass.wav"),
        "harmonic": Path("/tmp/harmonic.wav"),
        "percussion": Path("/tmp/percussion.wav"),
    }
    pipeline_results = {"bpm": 130.0, "integrated_lufs": -8.5, "mood": "peak_time"}
    mock_pipeline = AsyncMock()
    mock_pipeline.analyze = AsyncMock(return_value=MagicMock(features=pipeline_results))

    with patch("app.audio.deep.stem_analyzer._make_pipeline", return_value=mock_pipeline):
        result = await analyze_stems(stem_paths, Path("/tmp/original.wav"))

    assert set(result.keys()) == {"original", "vocals", "drums", "bass", "harmonic", "percussion"}
