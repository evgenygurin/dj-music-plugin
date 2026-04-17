"""Track aggregate: Track + Artist + Genre + Release + TrackExternalId + joins."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.base import Base
from app.v2.models.track import (
    Artist,
    Genre,
    Track,
    TrackArtist,
    TrackExternalId,
)


@pytest.mark.asyncio
async def test_track_minimal(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="Strobe")
    session.add(t)
    await session.commit()
    assert t.id is not None
    assert t.status == 0


@pytest.mark.asyncio
async def test_track_status_constraint(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session.add(Track(title="x", status=5))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_track_with_artist_via_join(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="Song")
    a = Artist(name="Deadmau5")
    session.add_all([t, a])
    await session.flush()
    session.add(TrackArtist(track_id=t.id, artist_id=a.id, role="primary"))
    await session.commit()

    rows = (
        (await session.execute(select(TrackArtist).where(TrackArtist.track_id == t.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].role == "primary"


@pytest.mark.asyncio
async def test_track_external_id_provider(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="Song")
    session.add(t)
    await session.flush()
    session.add(TrackExternalId(track_id=t.id, provider_code="yandex_music", external_id="98765"))
    await session.commit()
    rows = (
        (await session.execute(select(TrackExternalId).where(TrackExternalId.track_id == t.id)))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].external_id == "98765"


@pytest.mark.asyncio
async def test_genre_hierarchy(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    parent = Genre(name="Techno")
    session.add(parent)
    await session.flush()
    child = Genre(name="Peak Time Techno", parent_id=parent.id)
    session.add(child)
    await session.commit()
    loaded = await session.get(Genre, child.id)
    assert loaded is not None
    assert loaded.parent_id == parent.id
