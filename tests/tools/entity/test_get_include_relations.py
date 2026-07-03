"""``entity_get.include_relations`` — relations actually load (v1.6.1).

Regression: the parameter was validated against ``EntityConfig.relations``
but never used — ``repo.get(id)`` is a bare ``session.get`` and the
response ``data`` never contained the relation payload. Verified live
2026-07-03: ``entity_get(track, 146, include_relations=["features"])``
returned ``data`` without ``features`` even though the row existed in
``track_audio_features_computed``.

Fix: ``EntityConfig.relation_loaders`` — one async ``(uow, row)`` loader
per declared relation, wired in ``app/registry/defaults.py`` and awaited
by the dispatcher after field projection (so ``fields="summary"`` doesn't
strip an explicitly requested relation).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastmcp.client import Client
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.models.audio_file import DjBeatgrid
from app.models.playlist import DjPlaylistItem
from app.models.set import DjSetItem, DjSetVersion
from app.models.track import Artist, TrackArtist
from app.models.track_features import TrackAudioFeaturesComputed
from app.registry.defaults import (
    _load_audio_file_beatgrids,
    _load_playlist_items,
    _load_set_version_items,
    _load_set_versions,
    _load_track_artists,
    _load_track_features,
)
from app.repositories.audio_file import AudioFileRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository, SetVersionRepository
from app.repositories.track import TrackRepository
from app.repositories.track_features import TrackFeaturesRepository


class _UoW:
    """Minimal UoW stub carrying live repositories for loader tests."""

    def __init__(self, session: AsyncSession) -> None:
        self.tracks = TrackRepository(session)
        self.track_features = TrackFeaturesRepository(session)
        self.playlists = PlaylistRepository(session)
        self.sets = SetRepository(session)
        self.set_versions = SetVersionRepository(session)
        self.audio_files = AudioFileRepository(session)


@pytest_asyncio.fixture
async def uow(engine: AsyncEngine, session: AsyncSession) -> _UoW:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return _UoW(session)


@pytest.fixture
def db_session(uow: _UoW) -> AsyncSession:
    return uow.tracks.session


# ── per-relation loader tests (real SQLite, FK enforcement ON) ─────────


@pytest.mark.asyncio
async def test_track_features_relation_loads(uow: _UoW, db_session: AsyncSession) -> None:
    track = await uow.tracks.create(title="Spastik")
    db_session.add(
        TrackAudioFeaturesComputed(track_id=track.id, analysis_level=2, bpm=128.0, key_code=8)
    )
    await db_session.flush()

    payload = await _load_track_features(uow, track)
    assert payload is not None
    assert payload["bpm"] == 128.0
    assert payload["key_code"] == 8


@pytest.mark.asyncio
async def test_track_features_relation_none_when_unanalyzed(uow: _UoW) -> None:
    track = await uow.tracks.create(title="No Features Yet")
    assert await _load_track_features(uow, track) is None


@pytest.mark.asyncio
async def test_track_artists_relation_loads_primary_first(
    uow: _UoW, db_session: AsyncSession
) -> None:
    track = await uow.tracks.create(title="Collab")
    a1 = Artist(name="Remixer Guy")
    a2 = Artist(name="Main Act")
    db_session.add_all([a1, a2])
    await db_session.flush()
    db_session.add_all(
        [
            TrackArtist(track_id=track.id, artist_id=a1.id, role="remixer"),
            TrackArtist(track_id=track.id, artist_id=a2.id, role="primary"),
        ]
    )
    await db_session.flush()

    payload = await _load_track_artists(uow, track)
    assert [p["name"] for p in payload] == ["Main Act", "Remixer Guy"]
    assert payload[0] == {"artist_id": a2.id, "name": "Main Act", "role": "primary"}


@pytest.mark.asyncio
async def test_playlist_items_relation_loads_in_sort_order(
    uow: _UoW, db_session: AsyncSession
) -> None:
    tracks = [await uow.tracks.create(title=f"T{i}") for i in range(3)]
    pl = await uow.playlists.create(name="Crate")
    # Insert out of order to prove sort_index ordering.
    for sort_index, track in [(2, tracks[2]), (0, tracks[0]), (1, tracks[1])]:
        db_session.add(DjPlaylistItem(playlist_id=pl.id, track_id=track.id, sort_index=sort_index))
    await db_session.flush()

    payload = await _load_playlist_items(uow, pl)
    assert [p["track_id"] for p in payload] == [t.id for t in tracks]
    assert [p["sort_index"] for p in payload] == [0, 1, 2]


@pytest.mark.asyncio
async def test_set_versions_relation_loads(uow: _UoW, db_session: AsyncSession) -> None:
    dj_set = await uow.sets.create(name="Peak Hour")
    db_session.add_all(
        [
            DjSetVersion(set_id=dj_set.id, label="v1", quality_score=0.7),
            DjSetVersion(set_id=dj_set.id, label="v2", quality_score=0.85),
        ]
    )
    await db_session.flush()

    payload = await _load_set_versions(uow, dj_set)
    assert [p["label"] for p in payload] == ["v1", "v2"]
    assert payload[1]["quality_score"] == 0.85


@pytest.mark.asyncio
async def test_set_version_items_relation_loads(uow: _UoW, db_session: AsyncSession) -> None:
    tracks = [await uow.tracks.create(title=f"S{i}") for i in range(2)]
    dj_set = await uow.sets.create(name="Roller")
    version = DjSetVersion(set_id=dj_set.id, label="v1")
    db_session.add(version)
    await db_session.flush()
    db_session.add_all(
        [
            DjSetItem(version_id=version.id, track_id=tracks[0].id, sort_index=0),
            DjSetItem(version_id=version.id, track_id=tracks[1].id, sort_index=1),
        ]
    )
    await db_session.flush()

    payload = await _load_set_version_items(uow, version)
    assert [p["track_id"] for p in payload] == [tracks[0].id, tracks[1].id]
    assert payload[0]["sort_index"] == 0


@pytest.mark.asyncio
async def test_audio_file_beatgrids_relation_loads_canonical_first(
    uow: _UoW, db_session: AsyncSession
) -> None:
    track = await uow.tracks.create(title="Gridded")
    item = await uow.audio_files.create(
        track_id=track.id, file_path="/tmp/a.mp3", file_hash="deadbeef", file_size=1
    )
    db_session.add_all(
        [
            DjBeatgrid(library_item_id=item.id, bpm=127.5, canonical=False),
            DjBeatgrid(library_item_id=item.id, bpm=128.0, canonical=True),
        ]
    )
    await db_session.flush()

    payload = await _load_audio_file_beatgrids(uow, item)
    assert [p["bpm"] for p in payload] == [128.0, 127.5]
    assert payload[0]["canonical"] is True


# ── registry consistency: declared relations ⇔ loaders ─────────────────


def test_every_declared_relation_has_a_loader() -> None:
    """``relations`` is the advertised contract (schema://entities),
    ``relation_loaders`` its implementation — key sets must match on
    every entity or ``include_relations`` regresses to a silent no-op
    (or a call-time drift error)."""
    from app.registry.defaults import register_default_entities
    from app.registry.entity import EntityRegistry

    EntityRegistry.clear()
    register_default_entities()

    for name in EntityRegistry.names():
        cfg = EntityRegistry.get(name)
        assert set(cfg.relations.keys()) == set(cfg.relation_loaders.keys()), (
            f"entity {name!r}: relations {sorted(cfg.relations)} != "
            f"loaders {sorted(cfg.relation_loaders)}"
        )


# ── dispatcher wiring (tool layer, mocked UoW) ──────────────────────────


@pytest.mark.asyncio
async def test_entity_get_attaches_relation_payload(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    version = DjSetVersion(id=7, set_id=3, label="v1", quality_score=0.9)
    items = [
        DjSetItem(id=1, version_id=7, track_id=11, sort_index=0, pinned=False),
        DjSetItem(id=2, version_id=7, track_id=12, sort_index=1, pinned=True),
    ]
    mock_uow.set_versions.get = AsyncMock(return_value=version)
    mock_uow.set_versions.get_items = AsyncMock(return_value=items)

    result = await mcp_client.call_tool(
        "entity_get",
        {"entity": "set_version", "id": 7, "include_relations": ["items"]},
    )
    data = (result.structured_content or result.data)["data"]
    assert [i["track_id"] for i in data["items"]] == [11, 12]
    assert data["items"][1]["pinned"] is True


@pytest.mark.asyncio
async def test_entity_get_relations_survive_field_projection(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    """``fields="summary"`` projects the view — but a relation the caller
    explicitly asked for must still be attached."""
    version = DjSetVersion(id=7, set_id=3, label="v1", quality_score=0.9)
    mock_uow.set_versions.get = AsyncMock(return_value=version)
    mock_uow.set_versions.get_items = AsyncMock(return_value=[])

    result = await mcp_client.call_tool(
        "entity_get",
        {
            "entity": "set_version",
            "id": 7,
            "fields": "summary",
            "include_relations": ["items"],
        },
    )
    data = (result.structured_content or result.data)["data"]
    assert data["items"] == []
    assert data["label"] == "v1"
    assert "generator_run_meta" not in data  # projection still applied
