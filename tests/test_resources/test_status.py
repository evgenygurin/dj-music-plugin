"""Tests for status resources (status://library, status://platforms)."""

import json

import pytest

from app.controllers.resources.status import library_status, platforms_status
from app.core.constants import Provider
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.platform import YandexMetadata
from app.db.models.track import Track


@pytest.mark.asyncio
async def test_library_status_empty(db):
    """Test library status with no tracks."""
    result = await library_status(session=db)
    data = json.loads(result)

    assert data["total_tracks"] == 0
    assert data["active_tracks"] == 0
    assert data["archived_tracks"] == 0
    assert data["tracks_with_features"] == 0
    assert data["feature_coverage_percent"] == 0.0
    assert data["health"] == "empty"


@pytest.mark.asyncio
async def test_library_status_with_tracks(db):
    """Test library status with tracks and features."""
    # Create tracks
    track1 = Track(
        title="Test Track 1",
        sort_title="test track 1",
        duration_ms=180000,
        status=0,
    )
    track2 = Track(
        title="Test Track 2",
        sort_title="test track 2",
        duration_ms=240000,
        status=0,
    )
    track3 = Track(
        title="Archived Track",
        sort_title="archived track",
        duration_ms=200000,
        status=1,  # archived
    )
    db.add_all([track1, track2, track3])
    await db.flush()

    # Add features to track1
    features1 = TrackAudioFeaturesComputed(
        track_id=track1.id,
        bpm=128.5,
        key_code=14,  # 8A
        integrated_lufs=-12.5,
        energy_mean=0.7,
        spectral_centroid_hz=2500.0,
    )
    db.add(features1)
    await db.flush()

    result = await library_status(session=db)
    data = json.loads(result)

    assert data["total_tracks"] == 3
    assert data["active_tracks"] == 2
    assert data["archived_tracks"] == 1
    assert data["tracks_with_features"] == 1
    assert data["feature_coverage_percent"] == 33.3  # 1/3
    assert data["tracks_with_bpm"] == 1
    assert data["tracks_with_key"] == 1
    assert data["tracks_with_energy"] == 1
    assert data["health"] == "needs_analysis"


@pytest.mark.asyncio
async def test_library_status_good_health(db):
    """Test library status with high feature coverage (>80%)."""
    # Create 10 tracks
    tracks = [
        Track(
            title=f"Track {i}",
            sort_title=f"track {i}",
            duration_ms=180000,
            status=0,
        )
        for i in range(10)
    ]
    db.add_all(tracks)
    await db.flush()

    # Add features to 9 tracks (90% coverage)
    for i in range(9):
        features = TrackAudioFeaturesComputed(
            track_id=tracks[i].id,
            bpm=130.0,
            integrated_lufs=-10.0,
        )
        db.add(features)
    await db.flush()

    result = await library_status(session=db)
    data = json.loads(result)

    assert data["total_tracks"] == 10
    assert data["tracks_with_features"] == 9
    assert data["feature_coverage_percent"] == 90.0
    assert data["health"] == "good"


@pytest.mark.asyncio
async def test_platforms_status_empty(db):
    """Test platforms status with no linked tracks."""
    result = await platforms_status(session=db)
    data = json.loads(result)

    assert data["total_platforms"] == len(Provider)
    assert len(data["platforms"]) == 4

    # All platforms should have 0 linked tracks
    for platform in data["platforms"]:
        assert platform["linked_tracks"] == 0
        # configured flag varies by platform
        if platform["platform"] == Provider.YANDEX_MUSIC.value:
            assert platform["configured"] is True  # Assume configured
        else:
            assert platform["configured"] is False


@pytest.mark.asyncio
async def test_platforms_status_with_links(db):
    """Test platforms status with linked tracks."""
    # Create track
    track = Track(
        title="Test Track",
        sort_title="test track",
        duration_ms=180000,
        status=0,
    )
    db.add(track)
    await db.flush()

    # Add Yandex Music metadata
    ym_meta = YandexMetadata(
        track_id=track.id,
        yandex_track_id="12345",
        album_title="Test Album",
        duration_ms=180000,
    )
    db.add(ym_meta)
    await db.flush()

    result = await platforms_status(session=db)
    data = json.loads(result)

    # Find YM platform
    ym_platform = next(
        p for p in data["platforms"] if p["platform"] == Provider.YANDEX_MUSIC.value
    )
    assert ym_platform["linked_tracks"] == 1
    assert ym_platform["configured"] is True

    # Other platforms should still have 0
    for platform in data["platforms"]:
        if platform["platform"] != Provider.YANDEX_MUSIC.value:
            assert platform["linked_tracks"] == 0
