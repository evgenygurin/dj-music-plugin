"""Audit iter 46 (T-44): ``PlaylistView.item_count`` and
``SetView.version_count`` were declared in the View schemas but
permanently ``None`` because the dispatcher (``entity_get`` /
``entity_list``) read fields directly off the ORM row, and the
columns don't exist on the row.

Live confirmation:

    entity_get(playlist, 5) → {"item_count": null, ...}
    -- but the playlist has ~60 tracks
    entity_get(set, 5) → {"version_count": null, ...}
    -- but the set has 3 versions

Fix: ``EntityConfig.view_enricher`` optional callable — async
(uow, row, view_dict) → view_dict. Wired through ``entity_get``
and ``entity_list`` to populate derived fields after the View
validates. Tests below exercise both pathways with real
SQLAlchemy fixtures.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.models.playlist import DjPlaylistItem
from app.models.set import DjSetVersion
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository


@pytest_asyncio.fixture
async def repos(
    engine: AsyncEngine, session: AsyncSession
) -> tuple[PlaylistRepository, SetRepository, TrackRepository, AsyncSession]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return (
        PlaylistRepository(session),
        SetRepository(session),
        TrackRepository(session),
        session,
    )


@pytest.mark.asyncio
async def test_playlist_item_count_repo_method(
    repos: tuple[PlaylistRepository, SetRepository, TrackRepository, AsyncSession],
) -> None:
    """``PlaylistRepository.item_count`` returns the actual track count."""
    pl_repo, _, t_repo, session = repos
    tracks = [await t_repo.create(title=f"T{i}") for i in range(7)]
    pl = await pl_repo.create(name="Test Pool")
    for i, t in enumerate(tracks):
        session.add(DjPlaylistItem(playlist_id=pl.id, track_id=t.id, sort_index=i))
    await session.flush()

    assert await pl_repo.item_count(pl.id) == 7


@pytest.mark.asyncio
async def test_playlist_item_count_zero_for_empty(
    repos: tuple[PlaylistRepository, SetRepository, TrackRepository, AsyncSession],
) -> None:
    pl_repo, _, _, _ = repos
    pl = await pl_repo.create(name="Empty")
    assert await pl_repo.item_count(pl.id) == 0


@pytest.mark.asyncio
async def test_view_enricher_populates_playlist_item_count(
    repos: tuple[PlaylistRepository, SetRepository, TrackRepository, AsyncSession],
) -> None:
    """The enricher attached to the playlist EntityConfig fills
    ``item_count`` on the dumped View dict."""
    from app.registry.defaults import _enrich_playlist_view

    pl_repo, _, t_repo, session = repos
    tracks = [await t_repo.create(title=f"T{i}") for i in range(3)]
    pl = await pl_repo.create(name="Trio")
    for i, t in enumerate(tracks):
        session.add(DjPlaylistItem(playlist_id=pl.id, track_id=t.id, sort_index=i))
    await session.flush()

    # Mock UoW with the live repo attached at .playlists.
    class _UoW:
        playlists = pl_repo

    enriched = await _enrich_playlist_view(
        _UoW(),  # type: ignore[arg-type]
        pl,
        {"id": pl.id, "name": "Trio", "item_count": None},
    )
    assert enriched["item_count"] == 3


@pytest.mark.asyncio
async def test_view_enricher_populates_set_version_count(
    repos: tuple[PlaylistRepository, SetRepository, TrackRepository, AsyncSession],
) -> None:
    """The enricher attached to the set EntityConfig fills
    ``version_count`` on the dumped View dict."""
    from app.registry.defaults import _enrich_set_view

    _, set_repo, _, session = repos
    s = await set_repo.create(name="My Set")
    for i in range(2):
        session.add(DjSetVersion(set_id=s.id, label=f"v{i + 1}"))
    await session.flush()

    class _UoW:
        sets = set_repo

    enriched = await _enrich_set_view(
        _UoW(),  # type: ignore[arg-type]
        s,
        {"id": s.id, "name": "My Set", "version_count": None},
    )
    assert enriched["version_count"] == 2


@pytest.mark.asyncio
async def test_entity_config_exposes_view_enricher_field() -> None:
    """``EntityConfig.view_enricher`` is wired on playlist + set
    after ``register_default_entities`` runs."""
    from app.registry.defaults import register_default_entities
    from app.registry.entity import EntityRegistry

    EntityRegistry.clear()
    register_default_entities()

    pl_cfg = EntityRegistry.get("playlist")
    assert pl_cfg.view_enricher is not None

    set_cfg = EntityRegistry.get("set")
    assert set_cfg.view_enricher is not None

    # Other entities have no enricher (they don't need one yet).
    track_cfg = EntityRegistry.get("track")
    assert track_cfg.view_enricher is None
