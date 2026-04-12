"""Acceptance tests for the analysis flow."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models.audio import FeatureExtractionRun, TrackAudioFeaturesComputed, TrackSection
from app.db.models.library import DjLibraryItem
from app.db.models.track import Track
from tests.acceptance.conftest import parse_tool_result


@pytest.mark.asyncio
async def test_analysis_flow_persists_features_sections_and_run_metadata(
    acceptance_harness,
    patch_audio_pipeline,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "analysis-source.mp3"
    audio_path.write_bytes(b"analysis-audio")

    async with acceptance_harness.session_factory() as session:
        track = Track(title="Analysis Target", status=0, duration_ms=180000)
        session.add(track)
        await session.flush()
        track_id = track.id

        session.add(
            DjLibraryItem(
                track_id=track_id,
                file_path=str(audio_path),
                file_hash="deadbeef",
                file_size=audio_path.stat().st_size,
                mime_type="audio/mpeg",
                source_app="acceptance",
            )
        )
        await session.commit()

    # Audio tools are disabled at startup — unlock before calling
    await acceptance_harness.client.call_tool(
        "unlock_tools", {"action": "unlock", "category": "audio"},
    )

    result = await acceptance_harness.client.call_tool(
        "analyze_track",
        {"track_id": track_id, "analyzers": ["energy", "tempo"]},
    )
    data = parse_tool_result(result)

    assert data["status"] == "analyzed"
    assert data["mood"] == "driving"
    assert data["mood_confidence"] == 0.91

    async with acceptance_harness.session_factory() as session:
        features = await session.get(TrackAudioFeaturesComputed, track_id)
        assert features is not None
        assert features.bpm == 129.5
        assert features.mood == "driving"

        runs = (
            await session.execute(
                select(FeatureExtractionRun).where(FeatureExtractionRun.track_id == track_id)
            )
        ).scalars().all()
        assert len(runs) == 1
        assert runs[0].pipeline_name == "audio_service"

        sections = (
            await session.execute(select(TrackSection).where(TrackSection.track_id == track_id))
        ).scalars().all()
        assert len(sections) == 1
