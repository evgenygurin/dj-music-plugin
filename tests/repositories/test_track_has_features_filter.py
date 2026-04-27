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

from app.models import Base, Track, TrackAudioFeaturesComputed
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
    session.add(TrackAudioFeaturesComputed(track_id=with_feat.id, analysis_level=2))
    await session.flush()
    return repo, with_feat, without


@pytest.mark.asyncio
async def test_has_features_true_only_keeps_tracks_with_features(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    repo, with_feat, without = setup
    page = await repo.filter(where={"has_features__eq": True})
    ids = {t.id for t in page.items}
    assert ids == {with_feat.id}, f"only featured track expected, got {ids}"


@pytest.mark.asyncio
async def test_has_features_false_only_keeps_tracks_without_features(
    setup: tuple[TrackRepository, Track, Track],
) -> None:
    repo, with_feat, without = setup
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
    repo, with_feat, without = setup
    page = await repo.filter(
        where={
            "has_features__eq": True,
            "title__icontains": "with",
        }
    )
    ids = {t.id for t in page.items}
    assert ids == {with_feat.id}
