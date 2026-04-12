"""Workflow orchestration tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from dj_music.audio.level_config import AnalysisLevel
from dj_music.services.workflows import (
    AnalyzeTrackWorkflow,
    BuildSetWorkflow,
    DeliverSetWorkflow,
    ImportTracksWorkflow,
    SyncPlaylistWorkflow,
)


def _make_log(*, active: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        active=active,
        info=AsyncMock(),
        progress=AsyncMock(),
        elicit=AsyncMock(),
        set_total=AsyncMock(),
        set_message=AsyncMock(),
        increment=AsyncMock(),
        warn=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_import_tracks_auto_analyzes_and_logs_playlist_linking() -> None:
    import_service = AsyncMock()
    import_service.import_tracks.return_value = {
        "imported": 2,
        "skipped": 1,
        "enriched": 2,
        "playlist_added": 2,
        "id_mapping": {"111": 10, "222": 20},
    }
    tiered_pipeline = AsyncMock()
    tiered_pipeline.ensure_level.return_value = {"analyzed": 2, "failed": 0, "skipped": 0}
    workflow = ImportTracksWorkflow(import_service, tiered_pipeline)
    log = _make_log()

    result = await workflow.import_tracks(
        track_refs=["111", "222"],
        playlist_id=7,
        auto_analyze=True,
        log=log,
    )

    assert result["analysis"]["analyzed"] == 2
    import_service.import_tracks.assert_awaited_once_with(track_refs=["111", "222"], playlist_id=7)
    tiered_pipeline.ensure_level.assert_awaited_once_with([10, 20], AnalysisLevel.SCORING)
    assert log.info.await_args_list == [
        call("Import complete: 2 new, 1 skipped, 2 enriched"),
        call("Added 2 tracks to playlist 7"),
        call("Running L3 tiered analysis on 2 tracks..."),
    ]


@pytest.mark.asyncio
async def test_analyze_track_custom_analyzers_fall_back_to_tiered_pipeline() -> None:
    audio_service = AsyncMock()
    audio_service.analyze_track.return_value = {"error": "No audio file linked"}
    tiered_pipeline = AsyncMock()
    tiered_pipeline.ensure_level.return_value = {"analyzed": 1, "failed": 0, "skipped": 0}
    playlist_repo = AsyncMock()
    workflow = AnalyzeTrackWorkflow(audio_service, tiered_pipeline, playlist_repo)
    log = _make_log()

    result = await workflow.analyze_track(
        track_id=42,
        analyzers=["bpm", "key"],
        force=True,
        log=log,
    )

    assert result == {
        "track_id": 42,
        "level": int(AnalysisLevel.SCORING),
        "status": "analyzed",
        "analyzed": 1,
        "failed": 0,
        "skipped": 0,
    }
    audio_service.analyze_track.assert_awaited_once_with(
        42,
        analyzers=["bpm", "key"],
        force=True,
    )
    tiered_pipeline.ensure_level.assert_awaited_once_with(
        [42],
        AnalysisLevel.SCORING,
        force=True,
    )
    assert log.info.await_args_list == [
        call("Analyzing track 42 with custom analyzers..."),
        call("No local file — falling back to tiered pipeline..."),
    ]


@pytest.mark.asyncio
async def test_build_set_dry_run_ensures_scoring_without_building_real_set() -> None:
    set_service = AsyncMock()
    set_service.build_set_dry_run.return_value = {"preview": True, "candidate_count": 3}
    tiered_pipeline = AsyncMock()
    tiered_pipeline.ensure_level.return_value = {"analyzed": 3, "failed": 0, "skipped": 0}
    playlist_repo = AsyncMock()
    playlist_repo.get_track_ids.return_value = [11, 22, 33]
    workflow = BuildSetWorkflow(set_service, tiered_pipeline, playlist_repo)
    log = _make_log()

    result = await workflow.build_set(
        playlist_id=5,
        name="Warmup",
        template="opening",
        algorithm="greedy",
        dry_run=True,
        log=log,
    )

    assert result == {"preview": True, "candidate_count": 3}
    playlist_repo.get_track_ids.assert_awaited_once_with(5)
    tiered_pipeline.ensure_level.assert_awaited_once_with([11, 22, 33], AnalysisLevel.SCORING)
    set_service.build_set_dry_run.assert_awaited_once_with(
        playlist_id=5,
        template="opening",
        algorithm="greedy",
    )
    set_service.build_set.assert_not_called()
    assert log.info.await_args_list == [
        call("Building set 'Warmup' from playlist 5..."),
        call("Auto-analyzed 3 tracks (L3 scoring)"),
    ]
    assert log.progress.await_args_list == [call(0, 3)]


@pytest.mark.asyncio
async def test_score_transitions_for_set_ensures_latest_version_tracks() -> None:
    set_service = AsyncMock()
    set_service.get_latest_version.return_value = SimpleNamespace(id=9)
    set_service.get_version_items.return_value = [
        SimpleNamespace(track_id=101),
        SimpleNamespace(track_id=202),
        SimpleNamespace(track_id=303),
    ]
    set_service.score_set_transitions.return_value = {"scored": 2}
    tiered_pipeline = AsyncMock()
    tiered_pipeline.ensure_level.return_value = {"analyzed": 0, "failed": 0, "skipped": 3}
    playlist_repo = AsyncMock()
    workflow = BuildSetWorkflow(set_service, tiered_pipeline, playlist_repo)
    log = _make_log()

    result = await workflow.score_transitions(mode="set", set_id=77, log=log)

    assert result == {"scored": 2}
    set_service.get_latest_version.assert_awaited_once_with(77)
    set_service.get_version_items.assert_awaited_once_with(9)
    tiered_pipeline.ensure_level.assert_awaited_once_with(
        [101, 202, 303],
        AnalysisLevel.SCORING,
    )
    set_service.score_set_transitions.assert_awaited_once_with(77)
    log.info.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_set_dry_run_passes_version_label_to_delivery_service() -> None:
    delivery_service = AsyncMock()
    delivery_service.load_set_for_delivery.return_value = {
        "dj_set": SimpleNamespace(name="Peak Time"),
        "version": SimpleNamespace(label="v2"),
        "items": [SimpleNamespace(track_id=10), SimpleNamespace(track_id=20)],
    }
    delivery_service.score_delivery_transitions.return_value = (1, 0)
    tiered_pipeline = AsyncMock()
    tiered_pipeline.ensure_level.return_value = {"analyzed": 0, "failed": 0, "skipped": 2}
    workflow = DeliverSetWorkflow(delivery_service, tiered_pipeline)
    log = _make_log()

    result = await workflow.deliver_set(
        set_id=88,
        version="v2",
        dry_run=True,
        log=log,
    )

    assert result["dry_run"] is True
    assert result["version"] == "v2"
    delivery_service.load_set_for_delivery.assert_awaited_once_with(88, version_label="v2")
    delivery_service.build_export_data.assert_awaited_once_with(
        SimpleNamespace(name="Peak Time"),
        SimpleNamespace(label="v2"),
        [SimpleNamespace(track_id=10), SimpleNamespace(track_id=20)],
    )
    delivery_service.generate_exports.assert_not_called()
    assert log.info.await_args_list[:2] == [
        call("Starting delivery for set 88..."),
        call("Stage 1/4: Loaded 2 tracks"),
    ]


@pytest.mark.asyncio
async def test_deliver_set_syncs_to_ym_when_requested(tmp_path) -> None:
    delivery_service = AsyncMock()
    delivery_service.load_set_for_delivery.return_value = {
        "dj_set": SimpleNamespace(name="Club Set"),
        "version": SimpleNamespace(label="v1"),
        "items": [SimpleNamespace(track_id=1), SimpleNamespace(track_id=2)],
    }
    delivery_service.score_delivery_transitions.return_value = (1, 0)
    delivery_service.build_export_data.return_value = SimpleNamespace(tracks=[])
    delivery_service.generate_exports.return_value = [str(tmp_path / "club.m3u8")]
    tiered_pipeline = AsyncMock()
    tiered_pipeline.ensure_level.return_value = {"analyzed": 0, "failed": 0, "skipped": 2}
    sync_workflow = AsyncMock()
    sync_workflow.push_set_to_ym.return_value = {"ym_playlist_kind": 321, "tracks_pushed": 2}
    workflow = DeliverSetWorkflow(delivery_service, tiered_pipeline, sync_workflow)
    log = _make_log()

    result = await workflow.deliver_set(
        set_id=12,
        output_dir=str(tmp_path),
        copy_files=False,
        sync_to_ym=True,
        formats=["m3u8"],
        log=log,
    )

    assert result["synced_to_ym"] is True
    assert result["ym_sync"] == {"ym_playlist_kind": 321, "tracks_pushed": 2}
    sync_workflow.push_set_to_ym.assert_awaited_once_with(set_id=12, mode="auto")
    assert call("Syncing delivered set to Yandex Music...") in log.info.await_args_list


@pytest.mark.asyncio
async def test_deliver_set_aborts_when_user_declines_conflicts() -> None:
    delivery_service = AsyncMock()
    delivery_service.load_set_for_delivery.return_value = {
        "dj_set": SimpleNamespace(name="Risky Set"),
        "version": SimpleNamespace(label="v1"),
        "items": [SimpleNamespace(track_id=1), SimpleNamespace(track_id=2)],
    }
    delivery_service.score_delivery_transitions.return_value = (1, 1)
    tiered_pipeline = AsyncMock()
    tiered_pipeline.ensure_level.return_value = {"analyzed": 0, "failed": 0, "skipped": 2}
    workflow = DeliverSetWorkflow(delivery_service, tiered_pipeline)
    log = _make_log(active=True)
    log.elicit.return_value = SimpleNamespace(action="decline")

    result = await workflow.deliver_set(set_id=55, log=log)

    assert result == {
        "aborted": True,
        "reason": "User declined due to conflicts",
        "conflicts": 1,
    }
    delivery_service.build_export_data.assert_not_called()
    delivery_service.generate_exports.assert_not_called()
    log.elicit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_playlist_workflow_forwards_push_set_arguments() -> None:
    sync_service = AsyncMock()
    sync_service.push_set_to_ym.return_value = {"tracks_pushed": 5}
    workflow = SyncPlaylistWorkflow(sync_service)

    result = await workflow.push_set_to_ym(
        set_id=9,
        ym_playlist_name="Road Test",
        mode="create",
    )

    assert result == {"tracks_pushed": 5}
    sync_service.push_set_to_ym.assert_awaited_once_with(
        set_id=9,
        ym_playlist_name="Road Test",
        mode="create",
    )
