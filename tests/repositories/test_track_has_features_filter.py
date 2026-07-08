"""Regression: ``has_features`` magic filter on TrackRepository.

Audit (2026-04-27) found the filter rejected at the schema layer
(``extra_forbidden``) — schema fix landed first. This test pins the
runtime semantics promised by ``.claude/rules/repositories.md``:

    * ``has_features=True`` → INNER JOIN ``track_audio_features_computed``
      (only tracks with a features row)
    * ``has_features=False`` → NOT EXISTS subquery
      (only tracks WITHOUT a features row)
    * absent / None → no constraint (every track passes)
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, DjPlaylist, DjPlaylistItem, Track, TrackAudioFeaturesComputed
from app.repositories.track import TrackRepository


@pytest_asyncio.fixture
async def setup(
    engine: AsyncEngine, session: AsyncSession
) -> tuple[TrackRepository, Track, Track]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    repo = TrackRepository(session)
    with_feat = await repo.create(title="with-features")
    without = await repo.create(title="no-features")
    session.add(
        TrackAudioFeaturesComputed(
            track_id=with_feat.id,
            analysis_level=2,
            bpm=135.0,
            key_code=8,
            mood="industrial",
        )
    )
    await session.flush()
    return repo, with_feat, without


@pytest.mark.asyncio
async def test_has_features_true_only_keeps_tracks_with_features(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    repo, with_feat, _ = setup
    page = await repo.filter(where={"has_features__eq": True})
    ids = {t.id for t in page.items}
    assert ids == {with_feat.id}, f"only featured track expected, got {ids}"


@pytest.mark.asyncio
async def test_has_features_false_only_keeps_tracks_without_features(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    repo, _, without = setup
    page = await repo.filter(where={"has_features__eq": False})
    ids = {t.id for t in page.items}
    assert ids == {without.id}, f"only un-featured track expected, got {ids}"


@pytest.mark.asyncio
async def test_has_features_absent_returns_all(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    repo, with_feat, without = setup
    page = await repo.filter(where={})
    ids = {t.id for t in page.items}
    assert ids == {with_feat.id, without.id}


@pytest.mark.asyncio
async def test_has_features_none_returns_all(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    """Pydantic-validated dict may carry ``has_features__eq: None`` after
    ``normalize_bare_fields``; the repo must treat None as no constraint."""
    repo, with_feat, without = setup
    page = await repo.filter(where={"has_features__eq": None})
    ids = {t.id for t in page.items}
    assert ids == {with_feat.id, without.id}


@pytest.mark.asyncio
async def test_has_features_combines_with_other_filters(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    """``has_features`` must compose with ordinary lookups, not replace them."""
    repo, with_feat, _ = setup
    page = await repo.filter(
        where={
            "has_features__eq": True,
            "title__icontains": "with",
        }
    )
    ids = {t.id for t in page.items}
    assert ids == {with_feat.id}


@pytest.mark.asyncio
async def test_playlist_id_eq_only_keeps_tracks_from_playlist(
    setup: tuple[TrackRepository, Track, Track],
    session: AsyncSession,
) -> None:
    repo, _, in_playlist = setup
    playlist = DjPlaylist(name="crate")
    session.add(playlist)
    await session.flush()
    session.add(
        DjPlaylistItem(
            playlist_id=playlist.id,
            track_id=in_playlist.id,
            sort_index=0,
        )
    )
    await session.flush()

    page = await repo.filter(where={"playlist_id__eq": playlist.id})

    ids = {t.id for t in page.items}
    assert ids == {in_playlist.id}


@pytest.mark.asyncio
async def test_playlist_id_eq_combines_with_other_filters(
    setup: tuple[TrackRepository, Track, Track],
    session: AsyncSession,
) -> None:
    repo, with_feat, in_playlist = setup
    playlist = DjPlaylist(name="crate")
    session.add(playlist)
    await session.flush()
    session.add_all(
        [
            DjPlaylistItem(
                playlist_id=playlist.id,
                track_id=with_feat.id,
                sort_index=0,
            ),
            DjPlaylistItem(
                playlist_id=playlist.id,
                track_id=in_playlist.id,
                sort_index=1,
            ),
        ]
    )
    await session.flush()

    page = await repo.filter(
        where={
            "playlist_id__eq": playlist.id,
            "title__icontains": "no",
        }
    )

    ids = {t.id for t in page.items}
    assert ids == {in_playlist.id}


@pytest.mark.asyncio
async def test_feature_filters_apply_to_track_list(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    repo, with_feat, _ = setup

    page = await repo.filter(
        where={
            "bpm__gte": 130,
            "bpm__lte": 140,
            "mood__in": ["industrial", "hard_techno", "driving", "raw"],
        }
    )

    ids = {t.id for t in page.items}
    assert ids == {with_feat.id}


@pytest.mark.asyncio
async def test_feature_filters_combine_with_playlist_scope(
    setup: tuple[TrackRepository, Track, Track],
    session: AsyncSession,
) -> None:
    repo, with_feat, without = setup
    playlist = DjPlaylist(name="crate")
    session.add(playlist)
    await session.flush()
    session.add_all(
        [
            DjPlaylistItem(
                playlist_id=playlist.id,
                track_id=with_feat.id,
                sort_index=0,
            ),
            DjPlaylistItem(
                playlist_id=playlist.id,
                track_id=without.id,
                sort_index=1,
            ),
        ]
    )
    await session.flush()

    page = await repo.filter(
        where={
            "playlist_id__eq": playlist.id,
            "bpm__gte": 130,
            "bpm__lte": 140,
            "mood__in": ["industrial"],
        }
    )

    ids = {t.id for t in page.items}
    assert ids == {with_feat.id}


@pytest.mark.asyncio
async def test_feature_sort_orders_track_list(
    setup: tuple[TrackRepository, Track, Track],
    session: AsyncSession,
) -> None:
    repo, with_feat, _ = setup
    slower = await repo.create(title="slower")
    session.add(
        TrackAudioFeaturesComputed(
            track_id=slower.id,
            analysis_level=2,
            bpm=131.0,
            key_code=9,
            mood="industrial",
        )
    )
    await session.flush()

    page = await repo.filter(
        where={"bpm__gte": 120},
        order=["bpm_desc"],
    )

    assert [t.id for t in page.items] == [with_feat.id, slower.id]
