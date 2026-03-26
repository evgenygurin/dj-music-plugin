"""Tests for SetService — quality_score persistence and build/rebuild logic."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playlist import Playlist, PlaylistItem
from app.models.track import Track
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.set_service import SetService


def _make_set_service(db: AsyncSession) -> SetService:
    """Create SetService with all repos from a single session."""
    return SetService(
        set_repo=SetRepository(db),
        track_repo=TrackRepository(db),
        playlist_repo=PlaylistRepository(db),
        feature_repo=FeatureRepository(db),
        transition_repo=TransitionRepository(db),
    )


async def _seed_playlist_with_tracks(db: AsyncSession, count: int = 5) -> int:
    """Create a playlist with N tracks. Returns playlist_id."""
    playlist = Playlist(name="Test Playlist")
    db.add(playlist)
    await db.flush()

    for i in range(count):
        track = Track(title=f"Track {i + 1}", duration_ms=300000, status=0)
        db.add(track)
        await db.flush()
        db.add(PlaylistItem(playlist_id=playlist.id, track_id=track.id, sort_index=i))
    await db.flush()

    return playlist.id


# ── BUG 1: quality_score saved to SetVersion ────────────


@pytest.mark.asyncio
async def test_build_set_saves_quality_score(db: AsyncSession) -> None:
    """build_set should persist quality_score on the SetVersion row."""
    playlist_id = await _seed_playlist_with_tracks(db, count=3)
    svc = _make_set_service(db)

    dj_set, version, quality, _algo = await svc.build_set(
        playlist_id=playlist_id,
        name="Quality Test Set",
        algorithm="greedy",
    )

    # quality is None when no audio features — but quality_score column should match
    assert version.quality_score == quality

    # Re-fetch from DB to ensure it's persisted (not just in-memory)
    set_repo = SetRepository(db)
    refreshed = await set_repo.get_latest_version(dj_set.id)
    assert refreshed is not None
    assert refreshed.quality_score == quality


@pytest.mark.asyncio
async def test_build_set_quality_score_is_none_without_features(db: AsyncSession) -> None:
    """Without audio features, quality_score should be None (no crash)."""
    playlist_id = await _seed_playlist_with_tracks(db, count=3)
    svc = _make_set_service(db)

    _, version, quality, algo = await svc.build_set(
        playlist_id=playlist_id,
        name="No Features Set",
        algorithm="greedy",
    )

    assert quality is None
    assert version.quality_score is None
    assert algo == "playlist_order"
