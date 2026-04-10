"""Acceptance tests for the set-building flow."""

from __future__ import annotations

import pytest

from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.playlist import Playlist, PlaylistItem
from app.db.models.track import Track
from app.db.repositories.set import SetRepository
from app.db.repositories.transition import TransitionRepository
from tests.acceptance.conftest import parse_tool_result


@pytest.mark.asyncio
async def test_build_set_flow_creates_version_and_transition_scores(
    acceptance_harness,
    patch_tiered_noop,
) -> None:
    async with acceptance_harness.session_factory() as session:
        playlist = Playlist(name="Build Flow Playlist", source_of_truth="local")
        session.add(playlist)
        await session.flush()
        playlist_id = playlist.id

        track_ids: list[int] = []
        for index in range(3):
            track = Track(title=f"Build Track {index}", status=0, duration_ms=180000)
            session.add(track)
            await session.flush()
            track_ids.append(track.id)
            session.add(PlaylistItem(playlist_id=playlist_id, track_id=track.id, sort_index=index))
            session.add(
                TrackAudioFeaturesComputed(
                    track_id=track.id,
                    bpm=128.0 + index,
                    key_code=8 + index,
                    integrated_lufs=-8.0,
                    energy_mean=0.6 + (index * 0.05),
                    spectral_centroid_hz=2400.0 + (index * 100),
                    onset_rate=4.0 + (index * 0.1),
                    kick_prominence=0.6,
                )
            )
        await session.commit()

    built = await acceptance_harness.client.call_tool(
        "build_set",
        {"playlist_id": playlist_id, "name": "Acceptance Build Set", "algorithm": "greedy"},
    )
    built_data = parse_tool_result(built)

    assert built_data["set_id"] > 0
    assert built_data["version_id"] > 0
    assert built_data["track_count"] == 3
    assert built_data["quality_score"] is not None

    scored = await acceptance_harness.client.call_tool(
        "score_transitions",
        {"mode": "set", "set_id": built_data["set_id"]},
    )
    scored_data = parse_tool_result(scored)
    assert scored_data["total_transitions"] == 2
    assert scored_data["scored_transitions"] == 2

    async with acceptance_harness.session_factory() as session:
        set_repo = SetRepository(session)
        transition_repo = TransitionRepository(session)

        version = await set_repo.get_latest_version(built_data["set_id"])
        assert version is not None
        items = await set_repo.get_version_items(version.id)
        assert [item.sort_index for item in items] == [0, 1, 2]

        first_transition = await transition_repo.get_score(items[0].track_id, items[1].track_id)
        assert first_transition is not None
        assert first_transition.overall_quality is not None
