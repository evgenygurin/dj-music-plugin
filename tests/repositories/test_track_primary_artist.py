"""Regression: ``TrackRepository.get_primary_artist_name``.

Audit O-1: ``local://tracks/{id}`` returned ``primary_artist_name: null``
even when ``track_artists`` rows existed for the track. The view's
``from_attributes=True`` looked for an attribute that Track doesn't
expose; the resource needs an explicit fetch via the repository.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Artist, Base, Track, TrackArtist
from app.repositories.track import TrackRepository


@pytest_asyncio.fixture
async def setup(
    engine: AsyncEngine, session: AsyncSession
) -> tuple[TrackRepository, Track, Track]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    repo = TrackRepository(session)
    track_with = await repo.create(title="With Artist")
    track_solo = await repo.create(title="No Artist")
    artist_main = Artist(name="Amelie Lens")
    artist_remix = Artist(name="Charlotte de Witte")
    session.add_all([artist_main, artist_remix])
    await session.flush()
    session.add_all(
        [
            TrackArtist(track_id=track_with.id, artist_id=artist_remix.id, role="remixer"),
            TrackArtist(track_id=track_with.id, artist_id=artist_main.id, role="primary"),
        ]
    )
    await session.flush()
    return repo, track_with, track_solo


@pytest.mark.asyncio
async def test_primary_artist_returned_for_track_with_primary_role(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    repo, track_with, _ = setup
    name = await repo.get_primary_artist_name(track_with.id)
    assert name == "Amelie Lens"


@pytest.mark.asyncio
async def test_primary_artist_none_for_track_with_no_artists(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    repo, _, track_solo = setup
    assert await repo.get_primary_artist_name(track_solo.id) is None


@pytest.mark.asyncio
async def test_primary_artist_falls_back_to_first_artist_when_no_primary_role(
    setup: tuple[TrackRepository, Track, Track],
    session: AsyncSession,
) -> None:
    """Some imports tag every artist with ``role='artist'`` rather than
    ``primary``; resolver still returns *some* artist name to avoid the
    blank-line UI bug, deterministically by artist_id."""
    repo, _, track_solo = setup
    artist = Artist(name="The Solo Artist")
    session.add(artist)
    await session.flush()
    session.add(TrackArtist(track_id=track_solo.id, artist_id=artist.id, role="artist"))
    await session.flush()
    assert await repo.get_primary_artist_name(track_solo.id) == "The Solo Artist"
