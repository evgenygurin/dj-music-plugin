"""Acceptance tests for the import flow."""

from __future__ import annotations

import pytest

from app.db.models.playlist import Playlist
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.track import TrackRepository
from tests.acceptance.conftest import make_provider_track, parse_tool_result


@pytest.mark.asyncio
async def test_import_flow_creates_track_and_persists_metadata(acceptance_harness) -> None:
    async with acceptance_harness.session_factory() as session:
        playlist = Playlist(name="Import Flow Playlist", source_of_truth="local")
        session.add(playlist)
        await session.flush()
        playlist_id = playlist.id
        await session.commit()

    acceptance_harness.ym.get_tracks.return_value = [
        make_provider_track("1001", "Warehouse Signal", artist="Flow Artist")
    ]

    result = await acceptance_harness.client.call_tool(
        "import_tracks",
        {"track_refs": ["1001"], "playlist_id": playlist_id},
    )
    data = parse_tool_result(result)
    track_id = data["id_mapping"]["1001"]

    assert data["imported"] == 1
    assert data["skipped"] == 0
    assert data["enriched"] == 1
    assert data["playlist_added"] == 1

    async with acceptance_harness.session_factory() as session:
        track_repo = TrackRepository(session)
        playlist_repo = PlaylistRepository(session)

        track = await track_repo.get_by_id(track_id)
        assert track is not None
        assert track.title == "Warehouse Signal"
        assert track.duration_ms == 180000

        ext = await track_repo.get_external_id(track_id, "yandex_music")
        assert ext is not None
        assert ext.external_id == "1001"

        ym_meta = await track_repo.get_ym_metadata(track_id)
        assert ym_meta is not None
        assert ym_meta.album_title == "Acceptance Album"

        assert track_id in await playlist_repo.get_track_ids(playlist_id)
