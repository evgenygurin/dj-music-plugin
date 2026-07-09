from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.deep_analysis.orchestrator import L6AnalysisOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_runs_full_pipeline() -> None:
    uow = MagicMock()
    uow.audio_files = MagicMock()
    uow.audio_files.get_for_track = AsyncMock(return_value=MagicMock(file_path="/tmp/test.mp3"))
    uow.stem_features = MagicMock()
    uow.stem_features.upsert = AsyncMock()
    uow.track_embeddings = MagicMock()
    uow.track_embeddings.upsert = AsyncMock()
    uow.track_features = MagicMock()
    uow.track_features.save_track_section = AsyncMock()
    uow.cross_similarity = MagicMock()
    uow.cross_similarity.upsert = AsyncMock()

    orch = L6AnalysisOrchestrator(storage_client=MagicMock())

    with patch(
        "app.domain.deep_analysis.orchestrator.run_demucs",
        return_value={"vocals": None, "drums": None, "bass": None, "other": None},
    ), patch(
        "app.domain.deep_analysis.orchestrator.analyze_stems",
        new_callable=AsyncMock,
        return_value={"original": {"bpm": 128}, "vocals": {"energy": 0.5}, "drums": {"energy": 0.8}, "bass": {"energy": 0.6}, "other": {"energy": 0.3}},
    ), patch(
        "app.domain.deep_analysis.orchestrator.build_beatgrid",
        new_callable=AsyncMock,
    ), patch(
        "app.domain.deep_analysis.orchestrator.analyze_structure",
        return_value=[],
    ), patch(
        "app.domain.deep_analysis.orchestrator.build_embeddings",
        return_value={"full": None, "timbral": None, "harmonic": None, "rhythmic": None, "energy": None},
    ), patch(
        "app.domain.deep_analysis.orchestrator.upload_timeseries",
        new_callable=AsyncMock,
    ), patch(
        "app.domain.deep_analysis.orchestrator.upload_waveform",
        new_callable=AsyncMock,
    ), patch(
        "app.domain.deep_analysis.orchestrator.build_waveform",
        return_value=[0.5, 0.3, 0.8],
    ), patch(
        "app.domain.deep_analysis.orchestrator.Path.exists",
        return_value=True,
    ), patch(
        "app.domain.deep_analysis.orchestrator.Path.mkdir",
    ):
        result = await orch.run(track_id=1, uow=uow)

    assert result.track_id == 1
    assert result.level == 6
    assert uow.stem_features.upsert.call_count == 5
