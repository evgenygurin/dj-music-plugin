"""Tests for template resources (track://{id}/features, set://{id}/summary, etc)."""

import json
from typing import Any

import pytest


def _parse(result: str | dict[str, Any]) -> dict[str, Any]:
    """Parse resource result — handles both str (old) and dict (new) returns."""
    if isinstance(result, dict):
        return result
    return json.loads(result)


from app.controllers.resources.templates import (
    catalog_stats,
    playlist_status,
    set_summary,
    track_features,
)
from app.core.errors import NotFoundError
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.playlist import Playlist
from app.db.models.set import DjSet as DJSet
from app.db.models.set import SetVersion as DJSetVersion
from app.db.models.track import Track


@pytest.mark.asyncio
async def test_track_features_not_found(db):
    """Test track features for non-existent track."""
    with pytest.raises(NotFoundError, match="Track not found: 999"):
        await track_features(track_id=999, session=db)


@pytest.mark.asyncio
async def test_track_features_no_analysis(db):
    """Test track features when track exists but not analyzed."""
    track = Track(
        title="Unanalyzed Track",
        sort_title="unanalyzed track",
        duration_ms=180000,
        status=0,
    )
    db.add(track)
    await db.flush()

    result = await track_features(track_id=track.id, session=db)
    data = _parse(result)

    assert data["track_id"] == track.id
    assert data["title"] == "Unanalyzed Track"
    assert data["features_available"] is False
    assert "not yet analyzed" in data["message"]


@pytest.mark.asyncio
async def test_track_features_with_analysis(db):
    """Test track features with complete analysis."""
    track = Track(
        title="Analyzed Track",
        sort_title="analyzed track",
        duration_ms=240000,
        status=0,
    )
    db.add(track)
    await db.flush()

    features = TrackAudioFeaturesComputed(
        track_id=track.id,
        bpm=132.0,
        bpm_confidence=0.95,
        bpm_stability=0.88,
        key_code=14,  # 8A (A minor)
        key_confidence=0.82,
        integrated_lufs=-11.2,
        energy_mean=0.68,
        energy_max=0.92,
        spectral_centroid_hz=3200.0,
        spectral_flatness=0.12,
        spectral_rolloff_85=5500.0,
        kick_prominence=0.75,
        pulse_clarity=0.88,
        onset_rate=2.5,
    )
    db.add(features)
    await db.flush()

    result = await track_features(track_id=track.id, session=db)
    data = _parse(result)

    assert data["track_id"] == track.id
    assert data["title"] == "Analyzed Track"
    assert data["features_available"] is True
    assert data["tempo"]["bpm"] == 132.0
    assert data["tempo"]["confidence"] == 0.95
    assert data["key"]["code"] == 14
    assert "8A" in data["key"]["name"]
    assert "A minor" in data["key"]["name"]
    assert data["energy"]["lufs_integrated"] == -11.2
    assert data["spectral"]["centroid_hz"] == 3200.0
    assert data["rhythm"]["kick_prominence"] == 0.75


@pytest.mark.asyncio
async def test_set_summary_not_found(db):
    """Test set summary for non-existent set."""
    with pytest.raises(NotFoundError, match="DJ Set not found: 999"):
        await set_summary(set_id=999, session=db)


@pytest.mark.asyncio
async def test_set_summary_no_versions(db):
    """Test set summary when set exists but no versions."""
    dj_set = DJSet(
        name="Empty Set",
        description="No versions yet",
        target_duration_ms=3600000,
    )
    db.add(dj_set)
    await db.flush()

    result = await set_summary(set_id=dj_set.id, session=db)
    data = _parse(result)

    assert data["set_id"] == dj_set.id
    assert data["name"] == "Empty Set"
    assert data["has_versions"] is False
    assert "No versions generated yet" in data["message"]


@pytest.mark.asyncio
async def test_set_summary_with_version(db):
    """Test set summary with a version."""
    dj_set = DJSet(
        name="Test Set",
        description="Set with version",
        target_duration_ms=3600000,
    )
    db.add(dj_set)
    await db.flush()

    version = DJSetVersion(
        set_id=dj_set.id,
        label="v1",
        quality_score=0.85,
    )
    db.add(version)
    await db.flush()

    result = await set_summary(set_id=dj_set.id, session=db)
    data = _parse(result)

    assert data["set_id"] == dj_set.id
    assert data["name"] == "Test Set"
    assert data["has_versions"] is True
    assert data["latest_version"]["version_id"] == version.id
    assert data["latest_version"]["version_label"] == "v1"
    assert data["latest_version"]["quality_score"] == 0.85
    assert "problems" in data


@pytest.mark.asyncio
async def test_playlist_status_not_found(db):
    """Test playlist status for non-existent playlist."""
    with pytest.raises(NotFoundError, match="Playlist not found: 999"):
        await playlist_status(playlist_id=999, session=db)


@pytest.mark.asyncio
async def test_playlist_status_basic(db):
    """Test playlist status for existing playlist."""
    import json as _json

    playlist = Playlist(
        name="Test Playlist",
        source_of_truth="local",
        source_app="dj_music_plugin",
        platform_ids=_json.dumps({"yandex_music": "user:playlist"}),
    )
    db.add(playlist)
    await db.flush()

    result = await playlist_status(playlist_id=playlist.id, session=db)
    data = _parse(result)

    assert data["playlist_id"] == playlist.id
    assert data["name"] == "Test Playlist"
    assert data["source_of_truth"] == "local"
    assert data["source_app"] == "dj_music_plugin"
    platform_ids = data["platform_ids"]
    if isinstance(platform_ids, str):
        import json as _j

        platform_ids = _j.loads(platform_ids)
    assert platform_ids["yandex_music"] == "user:playlist"


@pytest.mark.skip(reason="catalog_stats mood filter requires mood field not yet in model")
@pytest.mark.asyncio
async def test_catalog_stats_no_filters(db):
    """Test catalog stats without filters."""
    # Create tracks with features
    for i in range(5):
        track = Track(
            title=f"Track {i}",
            sort_title=f"track {i}",
            duration_ms=180000,
            status=0,
        )
        db.add(track)
        await db.flush()

        features = TrackAudioFeaturesComputed(
            track_id=track.id,
            bpm=128.0 + i * 2,
            integrated_lufs=-12.0 + i * 0.5,
            energy_mean=0.5 + i * 0.05,
        )
        db.add(features)
    await db.flush()

    result = await catalog_stats(session=db)
    data = _parse(result)

    assert data["total_tracks"] == 5
    assert data["filters_applied"]["mood"] is None
    assert data["filters_applied"]["bpm_min"] is None
    assert data["filters_applied"]["bpm_max"] is None
    assert data["avg_bpm"] == 132.0  # (128+130+132+134+136)/5
    assert "mood_distribution" in data
    assert data["mood_distribution"]["driving"] == 3
    assert data["mood_distribution"]["peak_time"] == 2


@pytest.mark.skip(reason="catalog_stats mood filter requires mood field not yet in model")
@pytest.mark.asyncio
async def test_catalog_stats_with_mood_filter(db):
    """Test catalog stats filtered by mood."""
    # Create tracks with different moods
    for i, mood in enumerate(["driving", "driving", "peak_time"]):
        track = Track(
            title=f"Track {i}",
            sort_title=f"track {i}",
            duration_ms=180000,
            status=0,
        )
        db.add(track)
        await db.flush()

        features = TrackAudioFeaturesComputed(
            track_id=track.id,
            bpm=130.0,
            integrated_lufs=-10.0,
            mood=mood,
        )
        db.add(features)
    await db.flush()

    from app.core.constants import TechnoSubgenre

    result = await catalog_stats(mood=TechnoSubgenre.DRIVING, session=db)
    data = _parse(result)

    assert data["total_tracks"] == 2
    assert data["filters_applied"]["mood"] == "driving"
    # When mood filter is active, no mood_distribution
    assert "mood_distribution" not in data


@pytest.mark.skip(reason="catalog_stats mood filter requires mood field not yet in model")
@pytest.mark.asyncio
async def test_catalog_stats_with_bpm_range(db):
    """Test catalog stats filtered by BPM range."""
    for i in range(5):
        track = Track(
            title=f"Track {i}",
            sort_title=f"track {i}",
            duration_ms=180000,
            status=0,
        )
        db.add(track)
        await db.flush()

        features = TrackAudioFeaturesComputed(
            track_id=track.id,
            bpm=125.0 + i * 5,  # 125, 130, 135, 140, 145
            integrated_lufs=-10.0,
            mood="driving",
        )
        db.add(features)
    await db.flush()

    result = await catalog_stats(bpm_min=130.0, bpm_max=140.0, session=db)
    data = _parse(result)

    assert data["total_tracks"] == 3  # 130, 135, 140
    assert data["filters_applied"]["bpm_min"] == 130.0
    assert data["filters_applied"]["bpm_max"] == 140.0
    assert data["avg_bpm"] == 135.0  # (130+135+140)/3
