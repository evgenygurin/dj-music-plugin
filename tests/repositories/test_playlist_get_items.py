"""Regression: ``PlaylistRepository.get_items`` exists and returns rows.

Audit observation O-4: ``local://playlists/{id}/audit`` reported
``total_tracks: 0`` for non-empty playlists. Root cause was the resource
calling ``getattr(uow.playlists, "get_items", None)`` and falling back
to ``[]`` because the method was never declared. ``get_track_ids``
existed but the audit resource needs the items themselves to look up
features per slot.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, DjPlaylist, DjPlaylistItem, Track
from app.repositories.playlist import PlaylistRepository


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> PlaylistRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return PlaylistRepository(session)


@pytest.mark.asyncio
async def test_get_items_returns_ordered_rows(
    repo: PlaylistRepository, session: AsyncSession
) -> None:
    pl = DjPlaylist(name="set-1")
    session.add(pl)
    await session.flush()
    t_a = Track(title="A")
    t_b = Track(title="B")
    session.add_all([t_a, t_b])
    await session.flush()
    session.add_all(
        [
            DjPlaylistItem(playlist_id=pl.id, track_id=t_a.id, sort_index=0),
            DjPlaylistItem(playlist_id=pl.id, track_id=t_b.id, sort_index=1),
        ]
    )
    await session.flush()

    items = await repo.get_items(pl.id)
    assert [it.track_id for it in items] == [t_a.id, t_b.id]
    assert [it.sort_index for it in items] == [0, 1]


@pytest.mark.asyncio
async def test_get_items_empty_for_unknown_playlist(repo: PlaylistRepository) -> None:
    items = await repo.get_items(99999)
    assert items == []
