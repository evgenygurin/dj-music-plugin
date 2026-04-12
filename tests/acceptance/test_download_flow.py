"""Acceptance tests for the download flow."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db.repositories.track import TrackRepository
from tests.acceptance.conftest import make_ym_track, parse_tool_result


@pytest.mark.asyncio
async def test_download_flow_links_library_item_and_analysis_can_find_file(
    acceptance_harness,
    patch_audio_pipeline,
    tmp_path: Path,
) -> None:
    acceptance_harness.ym.get_tracks.return_value = [
        make_ym_track("2001", "Download Me", artist="Downloader")
    ]

    imported = await acceptance_harness.client.call_tool(
        "import_tracks",
        {"track_refs": ["2001"]},
    )
    imported_data = parse_tool_result(imported)
    track_id = imported_data["id_mapping"]["2001"]

    downloaded = await acceptance_harness.client.call_tool(
        "download_tracks",
        {"track_refs": [str(track_id)], "target_dir": str(tmp_path)},
    )
    download_data = parse_tool_result(downloaded)

    assert download_data["downloaded"] == 1
    assert download_data["linked_to_library"] == 1
    assert download_data["failed"] == 0

    async with acceptance_harness.session_factory() as session:
        track_repo = TrackRepository(session)
        library_item = await track_repo.get_library_item(track_id)
        assert library_item is not None
        assert library_item.file_path is not None
        assert Path(library_item.file_path).exists()

    # Audio tools are disabled at startup — unlock before calling
    await acceptance_harness.client.call_tool(
        "unlock_tools", {"action": "unlock", "category": "audio"},
    )

    analysis = await acceptance_harness.client.call_tool(
        "analyze_track",
        {"track_id": track_id, "analyzers": ["energy"]},
    )
    analysis_data = parse_tool_result(analysis)

    assert analysis_data["status"] == "analyzed"
    assert analysis_data["track_id"] == track_id
