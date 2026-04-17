"""DjLibraryItem + DjBeatgrid."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.v2.models.audio_file import DjBeatgrid, DjLibraryItem
from app.v2.models.base import Base
from app.v2.models.track import Track


@pytest.mark.asyncio
async def test_create_library_item(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    li = DjLibraryItem(
        track_id=t.id,
        file_path="/vault/track.mp3",
        file_size=4_000_000,
        mime_type="audio/mpeg",
        bitrate_kbps=320,
        sample_rate=44100,
        channels=2,
    )
    session.add(li)
    await session.commit()
    assert li.id is not None


@pytest.mark.asyncio
async def test_beatgrid_bpm_range(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    t = Track(title="x")
    session.add(t)
    await session.flush()
    li = DjLibraryItem(track_id=t.id, file_path="/x.mp3", file_size=1, mime_type="audio/mpeg")
    session.add(li)
    await session.flush()
    bg = DjBeatgrid(
        library_item_id=li.id,
        bpm=128.0,
        first_downbeat_ms=320.0,
        confidence=0.9,
        canonical=True,
    )
    session.add(bg)
    await session.commit()
    assert bg.id is not None
    assert bg.canonical is True
