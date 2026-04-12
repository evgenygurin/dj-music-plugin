"""Acceptance tests for the delivery flow."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from dj_music.models.audio import TrackAudioFeaturesComputed
from dj_music.models.export import AppExport
from dj_music.models.library import DjLibraryItem
from dj_music.models.playlist import Playlist, PlaylistItem
from dj_music.models.track import Track
from tests.acceptance.conftest import parse_tool_result


@pytest.mark.asyncio
async def test_delivery_flow_creates_export_artifacts_and_logs_metadata(
    acceptance_harness,
    patch_tiered_noop,
    tmp_path: Path,
) -> None:
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    async with acceptance_harness.session_factory() as session:
        playlist = Playlist(name="Delivery Flow Playlist", source_of_truth="local")
        session.add(playlist)
        await session.flush()
        playlist_id = playlist.id

        for index in range(3):
            track = Track(title=f"Delivery Track {index}", status=0, duration_ms=180000)
            session.add(track)
            await session.flush()
            audio_path = audio_dir / f"track-{index}.mp3"
            audio_path.write_bytes(b"1" * 4096)
            session.add(PlaylistItem(playlist_id=playlist_id, track_id=track.id, sort_index=index))
            session.add(
                DjLibraryItem(
                    track_id=track.id,
                    file_path=str(audio_path),
                    file_hash=f"hash-{index}",
                    file_size=audio_path.stat().st_size,
                    mime_type="audio/mpeg",
                    source_app="acceptance",
                )
            )
            session.add(
                TrackAudioFeaturesComputed(
                    track_id=track.id,
                    bpm=130.0 + index,
                    key_code=8 + index,
                    integrated_lufs=-8.0,
                    energy_mean=0.65 + (index * 0.03),
                    spectral_centroid_hz=2500.0,
                    onset_rate=4.2,
                    kick_prominence=0.7,
                )
            )
        await session.commit()

    built = await acceptance_harness.client.call_tool(
        "build_set",
        {"playlist_id": playlist_id, "name": "Acceptance Delivery Set", "algorithm": "greedy"},
    )
    built_data = parse_tool_result(built)

    await acceptance_harness.client.call_tool(
        "score_transitions",
        {"mode": "set", "set_id": built_data["set_id"]},
    )

    output_dir = tmp_path / "delivery-output"
    delivered = await acceptance_harness.client.call_tool(
        "deliver_set",
        {
            "set_id": built_data["set_id"],
            "output_dir": str(output_dir),
            "formats": ["m3u8", "json"],
            "copy_files": True,
        },
    )
    delivery_data = parse_tool_result(delivered)

    assert len(delivery_data["generated_files"]) == 2
    assert delivery_data["copied_audio_files"] == 3
    for path_str in delivery_data["generated_files"]:
        assert Path(path_str).exists()

    async with acceptance_harness.session_factory() as session:
        exports = (await session.execute(select(AppExport))).scalars().all()
        assert len(exports) >= 2
