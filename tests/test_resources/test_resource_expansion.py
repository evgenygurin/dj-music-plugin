"""Tests for expanded MCP resources (status/track/playlist/set/library/export/reference)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
from fastmcp.resources import ResourceResult

from app.controllers.resources.exports_recent import exports_recent
from app.controllers.resources.library_prep import library_prep_state
from app.controllers.resources.reference.key_graph import key_graph_reference
from app.controllers.resources.status import analysis_quality, provider_coverage, set_integrity
from app.controllers.resources.templates import (
    playlist_profile,
    set_diagnostics,
    track_identity,
    track_sections,
)
from app.controllers.resources.transition_score import transition_recipe
from app.db.models.audio import FeatureExtractionRun, TrackAudioFeaturesComputed, TrackSection
from app.db.models.export import AppExport
from app.db.models.key import Key, KeyEdge
from app.db.models.library import DjBeatgrid, DjCuePoint, DjLibraryItem, DjSavedLoop
from app.db.models.platform import SpotifyMetadata, YandexMetadata
from app.db.models.playlist import Playlist, PlaylistItem
from app.db.models.set import DjSet, SetFeedback, SetItem, SetVersion
from app.db.models.track import (
    Artist,
    Genre,
    Label,
    Release,
    Track,
    TrackArtist,
    TrackExternalId,
    TrackGenre,
    TrackRelease,
)
from app.db.models.track_feedback import TrackFeedback
from app.db.models.transition import Transition
from app.db.repositories.feature import FeatureRepository


def _parse(result: str | dict[str, Any] | ResourceResult) -> dict[str, Any]:
    if isinstance(result, ResourceResult):
        item = result.contents[0] if result.contents else None
        if item is None:
            return {}
        content = item.content
        if isinstance(content, dict):
            return content
        if isinstance(content, str):
            return json.loads(content)
        return dict(content) if content else {}
    if isinstance(result, dict):
        return result
    return json.loads(result)


@pytest.mark.asyncio
async def test_analysis_quality_reports_field_coverage(db):
    t1 = Track(title="A", status=0)
    t2 = Track(title="B", status=0)
    db.add_all([t1, t2])
    await db.flush()

    db.add(
        TrackAudioFeaturesComputed(
            track_id=t1.id,
            bpm=132.0,
            key_code=8,
            integrated_lufs=-10.0,
            mood="driving",
            first_downbeat_ms=64.0,
        )
    )
    db.add(
        FeatureExtractionRun(
            track_id=t1.id,
            pipeline_name="p",
            pipeline_version="1",
            status="completed",
        )
    )
    db.add(
        FeatureExtractionRun(
            track_id=t2.id,
            pipeline_name="p",
            pipeline_version="1",
            status="failed",
        )
    )
    await db.flush()

    data = _parse(await analysis_quality(session=db))
    assert data["totals"]["tracks"] == 2
    assert "phrase_boundaries_ms" in data["field_coverage"]
    assert data["pipeline_runs"]["total_runs"] == 2


@pytest.mark.asyncio
async def test_set_integrity_reports_linkage(db):
    t1 = Track(title="T1", status=0)
    t2 = Track(title="T2", status=0)
    db.add_all([t1, t2])
    await db.flush()

    dj_set = DjSet(name="Integrity")
    db.add(dj_set)
    await db.flush()
    version = SetVersion(
        set_id=dj_set.id,
        label="v1",
        quality_score=0.8,
        generator_run_meta='{"algo":"ga"}',
    )
    db.add(version)
    await db.flush()

    transition = Transition(
        from_track_id=t1.id,
        to_track_id=t2.id,
        overall_quality=0.7,
    )
    db.add(transition)
    await db.flush()

    db.add(
        SetItem(
            version_id=version.id,
            track_id=t1.id,
            sort_index=0,
            transition_id=transition.id,
            mix_in_point_ms=10_000,
            mix_out_point_ms=20_000,
            planned_eq='{"low":-2}',
            notes="ok",
            pinned=True,
        )
    )
    db.add(SetItem(version_id=version.id, track_id=t2.id, sort_index=1))
    db.add(SetFeedback(version_id=version.id, rating=4, feedback_type="crowd"))
    await db.flush()

    data = _parse(await set_integrity(session=db))
    assert data["totals"]["set_items"] == 2
    assert data["set_item_fields"]["with_transition_id"] == 1
    assert data["version_fields"]["with_quality_score"] == 1


@pytest.mark.asyncio
async def test_provider_coverage_reports_platform_counts(db):
    t1 = Track(title="T1", status=0)
    t2 = Track(title="T2", status=0)
    db.add_all([t1, t2])
    await db.flush()

    db.add(TrackExternalId(track_id=t1.id, platform="yandex_music", external_id="ym:1"))
    db.add(TrackExternalId(track_id=t2.id, platform="spotify", external_id="sp:2"))
    db.add(YandexMetadata(track_id=t1.id, yandex_track_id="1"))
    db.add(SpotifyMetadata(track_id=t2.id, spotify_track_id="2"))
    await db.flush()

    data = _parse(await provider_coverage(session=db))
    assert data["total_tracks"] == 2
    per_platform = {row["platform"]: row for row in data["per_platform"]}
    assert per_platform["yandex_music"]["external_ids"] == 1
    assert per_platform["spotify"]["metadata_rows"] == 1


@pytest.mark.asyncio
async def test_track_identity_returns_joined_context(db):
    track = Track(title="Identity", sort_title="identity", duration_ms=180000, status=0)
    db.add(track)
    await db.flush()

    db.add(
        TrackAudioFeaturesComputed(
            track_id=track.id,
            bpm=130.0,
            key_code=8,
            integrated_lufs=-10.5,
            mood="driving",
            mood_confidence=0.9,
            analysis_level=3,
        )
    )
    db.add(TrackFeedback(track_id=track.id, rating=5, status="liked", play_count=2, skip_count=0))
    db.add(YandexMetadata(track_id=track.id, yandex_track_id="ym123", album_title="Album"))
    db.add(TrackExternalId(track_id=track.id, platform="yandex_music", external_id="ym123"))

    artist = Artist(name="Artist One")
    genre = Genre(name="Techno")
    label = Label(name="Label One")
    db.add_all([artist, genre, label])
    await db.flush()
    release = Release(title="Release One", label_id=label.id, release_date=date(2024, 1, 1))
    db.add(release)
    await db.flush()

    db.add(TrackArtist(track_id=track.id, artist_id=artist.id, role="main"))
    db.add(TrackGenre(track_id=track.id, genre_id=genre.id))
    db.add(TrackRelease(track_id=track.id, release_id=release.id, track_number=1))
    await db.flush()

    data = _parse(await track_identity(track_id=track.id, session=db))
    assert data["track"]["id"] == track.id
    assert data["artists"][0]["name"] == "Artist One"
    assert data["genres"][0]["name"] == "Techno"
    assert data["external_ids"]["yandex_music"] == "ym123"
    assert data["feedback"]["status"] == "liked"
    assert data["analysis_summary"]["mood"] == "driving"


@pytest.mark.asyncio
async def test_track_sections_supports_pagination_and_filter(db):
    track = Track(title="Sections", status=0)
    db.add(track)
    await db.flush()

    db.add_all(
        [
            TrackSection(track_id=track.id, section_type=1, start_ms=0, end_ms=1000, energy=0.2),
            TrackSection(
                track_id=track.id, section_type=2, start_ms=1000, end_ms=2000, energy=0.4
            ),
            TrackSection(
                track_id=track.id, section_type=2, start_ms=2000, end_ms=3500, energy=0.6
            ),
        ]
    )
    await db.flush()

    paged = _parse(await track_sections(track_id=track.id, limit=2, offset=1, session=db))
    assert paged["pagination"]["total"] == 3
    assert paged["pagination"]["returned"] == 2

    filtered = _parse(await track_sections(track_id=track.id, section_type=1, session=db))
    assert filtered["pagination"]["total"] == 1
    assert filtered["sections"][0]["section_type"] == 1


@pytest.mark.asyncio
async def test_playlist_profile_aggregates_features_and_entities(db):
    t1 = Track(title="A", status=0, duration_ms=180000)
    t2 = Track(title="B", status=0, duration_ms=200000)
    db.add_all([t1, t2])
    await db.flush()

    db.add_all(
        [
            TrackAudioFeaturesComputed(
                track_id=t1.id, bpm=128.0, integrated_lufs=-11.0, mood="driving", key_code=8
            ),
            TrackAudioFeaturesComputed(
                track_id=t2.id, bpm=132.0, integrated_lufs=-9.0, mood="peak_time", key_code=9
            ),
        ]
    )

    artist = Artist(name="Artist")
    genre = Genre(name="Techno")
    db.add_all([artist, genre])
    await db.flush()
    db.add_all(
        [
            TrackArtist(track_id=t1.id, artist_id=artist.id, role="main"),
            TrackArtist(track_id=t2.id, artist_id=artist.id, role="main"),
            TrackGenre(track_id=t1.id, genre_id=genre.id),
            TrackGenre(track_id=t2.id, genre_id=genre.id),
        ]
    )

    playlist = Playlist(
        name="Profile", source_of_truth="local", platform_ids='{"yandex_music":"42"}'
    )
    db.add(playlist)
    await db.flush()
    db.add_all(
        [
            PlaylistItem(playlist_id=playlist.id, track_id=t1.id, sort_index=0),
            PlaylistItem(playlist_id=playlist.id, track_id=t2.id, sort_index=1),
        ]
    )
    await db.flush()

    data = _parse(await playlist_profile(playlist_id=playlist.id, limit=1, offset=0, session=db))
    assert data["totals"]["tracks"] == 2
    assert data["totals"]["feature_rows"] == 2
    assert "driving" in data["mood_distribution"]
    assert data["track_sample"]["returned"] == 1


@pytest.mark.asyncio
async def test_set_diagnostics_returns_quality_and_feedback(db):
    t1 = Track(title="D1", status=0)
    t2 = Track(title="D2", status=0)
    db.add_all([t1, t2])
    await db.flush()
    db.add(TrackAudioFeaturesComputed(track_id=t1.id, bpm=130.0, key_code=8, integrated_lufs=-10))

    dj_set = DjSet(name="Diag Set")
    db.add(dj_set)
    await db.flush()
    version = SetVersion(set_id=dj_set.id, label="vA", quality_score=0.7)
    db.add(version)
    await db.flush()

    transition = Transition(
        from_track_id=t1.id,
        to_track_id=t2.id,
        overall_quality=0.4,
        hard_reject=False,
    )
    db.add(transition)
    await db.flush()

    db.add_all(
        [
            SetItem(
                version_id=version.id, track_id=t1.id, sort_index=0, transition_id=transition.id
            ),
            SetItem(version_id=version.id, track_id=t2.id, sort_index=1),
            SetFeedback(version_id=version.id, rating=3, feedback_type="crowd"),
        ]
    )
    await db.flush()

    data_latest = _parse(await set_diagnostics(set_id=dj_set.id, session=db))
    assert data_latest["version"]["id"] == version.id
    assert data_latest["transitions"]["rows"] == 1
    assert len(data_latest["transitions"]["weak_transitions"]) == 1

    data_label = _parse(await set_diagnostics(set_id=dj_set.id, version="vA", session=db))
    assert data_label["version"]["label"] == "vA"


@pytest.mark.asyncio
async def test_transition_recipe_returns_stored_recipe(db):
    t1 = Track(title="R1", status=0)
    t2 = Track(title="R2", status=0)
    db.add_all([t1, t2])
    await db.flush()
    db.add_all(
        [
            TrackAudioFeaturesComputed(track_id=t1.id, bpm=130.0, key_code=8, integrated_lufs=-10),
            TrackAudioFeaturesComputed(track_id=t2.id, bpm=132.0, key_code=9, integrated_lufs=-9),
        ]
    )
    transition = Transition(
        from_track_id=t1.id,
        to_track_id=t2.id,
        overall_quality=0.8,
        fx_type="eq_swap",
        transition_bars=16,
        transition_recipe_json='{"recipe":"swap bass on phrase"}',
    )
    db.add(transition)
    await db.flush()

    data = _parse(
        await transition_recipe(
            from_id=t1.id,
            to_id=t2.id,
            feat_repo=FeatureRepository(db),
            session=db,
        )
    )
    assert data["exists"] is True
    assert data["recipe"]["fx_type"] == "eq_swap"


@pytest.mark.asyncio
async def test_library_prep_state_reports_readiness(db):
    track = Track(title="Prep", status=0)
    db.add(track)
    await db.flush()
    item = DjLibraryItem(
        track_id=track.id,
        file_path="/tmp/prep.wav",
        file_hash="x" * 64,
        file_size=12345,
        mime_type="audio/wav",
        source_app="rekordbox",
    )
    db.add(item)
    await db.flush()
    beatgrid = DjBeatgrid(
        library_item_id=item.id,
        bpm=130.0,
        first_downbeat_ms=20.0,
        confidence=0.9,
        variable_tempo=True,
        canonical=True,
    )
    db.add(beatgrid)
    await db.flush()
    db.add(DjCuePoint(library_item_id=item.id, position_ms=1000.0, kind=1))
    db.add(DjSavedLoop(library_item_id=item.id, in_position_ms=1000.0, out_position_ms=2000.0))
    await db.flush()

    data = _parse(await library_prep_state(session=db))
    assert data["totals"]["library_items"] == 1
    assert data["totals"]["with_canonical_beatgrid"] == 1
    assert data["totals"]["with_cue_points"] == 1
    assert data["totals"]["with_saved_loops"] == 1


@pytest.mark.asyncio
async def test_exports_recent_returns_latest_rows(db):
    playlist = Playlist(name="Exp", source_of_truth="local")
    db.add(playlist)
    await db.flush()
    db.add_all(
        [
            AppExport(
                target_app="rekordbox",
                export_format="m3u",
                playlist_id=playlist.id,
                file_path="/tmp/a.m3u",
                file_size=100,
            ),
            AppExport(
                target_app="serato",
                export_format="csv",
                playlist_id=playlist.id,
                file_path="/tmp/b.csv",
                file_size=200,
            ),
        ]
    )
    await db.flush()

    data = _parse(await exports_recent(limit=1, session=db))
    assert data["returned"] == 1
    assert len(data["exports"]) == 1


@pytest.mark.asyncio
async def test_key_graph_reference_returns_nodes_and_edges(db):
    db.add_all(
        [
            Key(key_code=0, pitch_class=0, mode=0, name="C minor", camelot="5A"),
            Key(key_code=1, pitch_class=1, mode=1, name="C# major", camelot="3B"),
        ]
    )
    await db.flush()
    db.add(KeyEdge(from_key_code=0, to_key_code=1, distance=1, weight=0.9, rule_name="adjacent"))
    await db.flush()

    data = _parse(await key_graph_reference(session=db))
    assert data["total_keys"] == 2
    assert data["total_edges"] == 1
    assert data["distance_distribution"]["1"] == 1 or data["distance_distribution"][1] == 1
