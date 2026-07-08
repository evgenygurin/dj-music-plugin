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

from unittest.mock import AsyncMock, MagicMock

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
    """``EntityConfig.view_enricher`` is wired on playlist, set, and track
    after ``register_default_entities`` runs.

    ``track`` got its enricher in the 2026-05-07 smoke-test fix so that
    ``entity_get(track, …)`` and ``entity_list(track, …)`` populate
    ``primary_artist_name`` instead of returning ``null`` (the
    ``local://tracks/{id}`` resource had been doing this since audit
    O-1, but the entity dispatcher path was blind to it).
    """
    from app.registry.defaults import register_default_entities
    from app.registry.entity import EntityRegistry

    EntityRegistry.clear()
    register_default_entities()

    pl_cfg = EntityRegistry.get("playlist")
    assert pl_cfg.view_enricher is not None

    set_cfg = EntityRegistry.get("set")
    assert set_cfg.view_enricher is not None

    track_cfg = EntityRegistry.get("track")
    assert track_cfg.view_enricher is not None

    # Entities without derived view fields still have no enricher.
    feedback_cfg = EntityRegistry.get("track_feedback")
    assert feedback_cfg.view_enricher is None


@pytest.mark.asyncio
async def test_track_list_enricher_uses_bulk_artist_lookup() -> None:
    """``entity_list(track, ...)`` must not issue one artist query per row.

    The per-row path made user-visible list calls fragile: one stale asyncpg
    connection during any individual artist lookup leaked a raw SQL traceback
    and failed the whole response.
    """
    from app.registry.defaults import _enrich_track_views

    uow = MagicMock()
    uow.tracks.get_primary_artist_names = AsyncMock(return_value={1: "Dax J", 2: None})
    uow.tracks.get_primary_artist_name = AsyncMock(
        side_effect=AssertionError("entity_list(track) must use bulk artist lookup")
    )
    rows = [MagicMock(id=1), MagicMock(id=2)]
    views = [
        {"id": 1, "title": "Opressor", "primary_artist_name": None},
        {"id": 2, "title": "Untitled", "primary_artist_name": None},
    ]

    enriched = await _enrich_track_views(
        uow, rows, views, projection={"id", "title", "primary_artist_name"}
    )

    assert [v["primary_artist_name"] for v in enriched] == ["Dax J", None]
    uow.tracks.get_primary_artist_names.assert_awaited_once_with([1, 2])
    uow.tracks.get_primary_artist_name.assert_not_awaited()


@pytest.mark.asyncio
async def test_track_list_enricher_populates_feature_fields() -> None:
    """``entity_list(track, fields=[...])`` exposes common feature summary fields."""
    from types import SimpleNamespace

    from app.registry.defaults import _enrich_track_views

    uow = MagicMock()
    uow.tracks.get_primary_artist_names = AsyncMock(return_value={1: "Dax J"})
    uow.track_features.get_scoring_features_batch = AsyncMock(
        return_value={
            1: SimpleNamespace(
                bpm=132.5,
                key_code=8,
                mood="industrial",
                beatport_camelot=None,
            )
        }
    )
    rows = [MagicMock(id=1)]
    views = [
        {
            "id": 1,
            "title": "Opressor",
            "primary_artist_name": None,
            "artists": None,
            "bpm": None,
            "key_code": None,
            "camelot": None,
            "mood": None,
        }
    ]

    enriched = await _enrich_track_views(
        uow,
        rows,
        views,
        projection={"artists", "bpm", "key_code", "camelot", "mood"},
    )

    assert enriched[0]["artists"] == ["Dax J"]
    assert enriched[0]["bpm"] == 132.5
    assert enriched[0]["key_code"] == 8
    assert enriched[0]["camelot"] == "5A"
    assert enriched[0]["mood"] == "industrial"
    uow.tracks.get_primary_artist_names.assert_awaited_once_with([1])
    uow.track_features.get_scoring_features_batch.assert_awaited_once_with([1])
