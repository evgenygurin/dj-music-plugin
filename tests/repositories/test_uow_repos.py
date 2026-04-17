"""UoW exposes all 16 repos as lazy properties."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from app.models import Base
from app.repositories.track import TrackRepository
from app.repositories.unit_of_work import UnitOfWork


@pytest_asyncio.fixture
async def factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_uow_tracks_attr_is_repo(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as s, UnitOfWork(s) as uow:
        assert isinstance(uow.tracks, TrackRepository)
        t = await uow.tracks.create(title="hi")
        assert t.id is not None


@pytest.mark.asyncio
async def test_uow_all_repos_present(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as s, UnitOfWork(s) as uow:
        for attr in (
            "tracks",
            "playlists",
            "sets",
            "set_versions",
            "audio_files",
            "track_features",
            "transitions",
            "transition_history",
            "track_feedback",
            "track_affinity",
            "scoring_profiles",
            "provider_metadata",
            "yandex_metadata",
            "raw_provider_responses",
            "keys",
            "key_edges",
        ):
            assert hasattr(uow, attr), f"UoW missing {attr}"


@pytest.mark.asyncio
async def test_uow_repo_cached(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as s, UnitOfWork(s) as uow:
        assert uow.tracks is uow.tracks  # same instance via cached_property
