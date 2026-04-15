"""Tests for library://snapshot aggregation resource."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_snapshot_empty_db(db: AsyncSession):
    """Snapshot on empty DB returns valid structure with zero counts."""
    from app.controllers.resources.snapshot import library_snapshot

    result = await library_snapshot(session=db)
    data = json.loads(result)

    assert "total_tracks" in data
    assert "tracks_with_features" in data
    assert "mood_distribution" in data
    assert "playlists" in data
    assert "last_analyzed" in data
    assert data["total_tracks"] == 0
    assert data["mood_distribution"] == {}


@pytest.mark.asyncio
async def test_snapshot_with_tracks(db: AsyncSession, async_engine):
    """Snapshot returns correct mood distribution when tracks exist."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.controllers.resources.snapshot import library_snapshot
    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        t1 = Track(title="Detroit Track")
        t2 = Track(title="Industrial Track")
        t3 = Track(title="No Mood Track")
        session.add_all([t1, t2, t3])
        await session.flush()
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t1.id, bpm=132.0, mood="detroit", integrated_lufs=-11.5
            )
        )
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t2.id, bpm=140.0, mood="industrial", integrated_lufs=-10.0
            )
        )
        await session.commit()

    result = await library_snapshot(session=db)
    data = json.loads(result)
    assert data["total_tracks"] == 3
    assert data["tracks_with_features"] == 2
    assert data["mood_distribution"].get("detroit", 0) == 1
    assert data["mood_distribution"].get("industrial", 0) == 1


@pytest.mark.asyncio
async def test_snapshot_playlists(db: AsyncSession, async_engine):
    """Snapshot includes playlist list with track counts."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.controllers.resources.snapshot import library_snapshot
    from app.db.models.playlist import Playlist, PlaylistItem
    from app.db.models.track import Track

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        pl = Playlist(name="Dark Rollers")
        session.add(pl)
        await session.flush()
        t = Track(title="Test")
        session.add(t)
        await session.flush()
        session.add(PlaylistItem(playlist_id=pl.id, track_id=t.id, sort_index=0))
        await session.commit()

    result = await library_snapshot(session=db)
    data = json.loads(result)
    assert len(data["playlists"]) == 1
    assert data["playlists"][0]["name"] == "Dark Rollers"
    assert data["playlists"][0]["track_count"] == 1
