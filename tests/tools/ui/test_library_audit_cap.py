"""Audit iter 2: ``ui_library_audit`` whole-library scope was hardcoded
to ``limit=500``, silently truncating to ~2% of a 24k-track library.

Live MCP probe returned ``total_tracks: 500`` and the caller had no
way to know they saw a sample, not the library. Now the cap is
configurable, defaults to 5000, and the response carries ``truncated``
+ ``library_size`` + ``limit`` so consumers can detect the situation.
Per-playlist scope is still bounded by membership and ignores ``limit``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, Track, TrackAudioFeaturesComputed
from app.repositories.track import TrackRepository
from app.repositories.track_features import TrackFeaturesRepository
from app.tools.ui import library_audit as la_mod


class _Uow:
    def __init__(self, session: AsyncSession) -> None:
        from app.repositories.playlist import PlaylistRepository

        self.tracks = TrackRepository(session)
        self.track_features = TrackFeaturesRepository(session)
        self.playlists = PlaylistRepository(session)


@pytest_asyncio.fixture
async def seeded_uow(engine: AsyncEngine, session: AsyncSession) -> _Uow:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    for _ in range(15):
        t = Track(title="x")
        session.add(t)
        await session.flush()
        session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=128.0, key_code=14, mood="acid"))
    await session.flush()
    return _Uow(session)


@pytest.mark.asyncio
async def test_default_limit_caps_whole_library(seeded_uow: _Uow) -> None:
    data = await la_mod._gather(seeded_uow, playlist_id=None, limit=10)  # type: ignore[arg-type]
    assert data["total_tracks"] == 10
    assert data["truncated"] is True
    assert data["library_size"] == 15
    assert data["limit"] == 10


@pytest.mark.asyncio
async def test_explicit_limit_above_library_size_returns_all(seeded_uow: _Uow) -> None:
    data = await la_mod._gather(seeded_uow, playlist_id=None, limit=5000)  # type: ignore[arg-type]
    assert data["total_tracks"] == 15
    assert data["truncated"] is False
    assert data["library_size"] == 15
    assert data["limit"] == 5000


@pytest.mark.asyncio
async def test_per_playlist_scope_ignores_limit_and_truncated_flag(
    seeded_uow: _Uow, session: AsyncSession
) -> None:
    """Playlist scope is bounded by membership — ``truncated`` is None."""
    from app.models import DjPlaylist, DjPlaylistItem

    pl = DjPlaylist(name="x")
    session.add(pl)
    await session.flush()
    # Reuse first 3 seeded tracks.
    track_ids = [t.id for t in (await seeded_uow.tracks.filter(limit=3)).items]
    session.add_all(
        [
            DjPlaylistItem(playlist_id=pl.id, track_id=tid, sort_index=i)
            for i, tid in enumerate(track_ids)
        ]
    )
    await session.flush()

    data = await la_mod._gather(seeded_uow, playlist_id=pl.id, limit=10)  # type: ignore[arg-type]
    assert data["total_tracks"] == 3
    assert data["truncated"] is None
    assert data["library_size"] is None
    assert data["limit"] is None
