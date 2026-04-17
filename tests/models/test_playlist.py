"""DjPlaylist + DjPlaylistItem."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.base import Base
from app.models.playlist import DjPlaylist, DjPlaylistItem
from app.models.track import Track


@pytest.mark.asyncio
async def test_create_playlist(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    pl = DjPlaylist(name="Peak Hour", source_of_truth="local")
    session.add(pl)
    await session.commit()
    assert pl.id is not None
    assert pl.source_of_truth == "local"


@pytest.mark.asyncio
async def test_playlist_item_sort_index(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    pl = DjPlaylist(name="P")
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([pl, t1, t2])
    await session.flush()
    session.add_all(
        [
            DjPlaylistItem(playlist_id=pl.id, track_id=t1.id, sort_index=0),
            DjPlaylistItem(playlist_id=pl.id, track_id=t2.id, sort_index=1),
        ]
    )
    await session.commit()
    items = (
        (
            await session.execute(
                select(DjPlaylistItem)
                .where(DjPlaylistItem.playlist_id == pl.id)
                .order_by(DjPlaylistItem.sort_index)
            )
        )
        .scalars()
        .all()
    )
    assert [i.track_id for i in items] == [t1.id, t2.id]
