"""Audit iter 37 (T-35): two repo methods that backed
``local://tracks/{id}/suggest_next`` and
``local://tracks/{id}/suggest_replacement`` were never implemented,
so the resources always returned empty candidates with placeholder
reasons:

* ``transitions repository does not expose list_from yet``
* ``tracks repository does not expose search_by_bpm_range yet``

Those reasons shipped from v1.0 onwards; the suggest paths were
effectively dead even for tracks that DID have logged transitions
or BPM-compatible alternatives in the library.

Now both methods exist; these tests exercise them directly.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.models.track_features import TrackAudioFeaturesComputed
from app.models.transition import Transition
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository


@pytest_asyncio.fixture
async def repos(
    engine: AsyncEngine,
    session: AsyncSession,
) -> tuple[TrackRepository, TransitionRepository, AsyncSession]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return TrackRepository(session), TransitionRepository(session), session


@pytest.mark.asyncio
async def test_list_from_returns_transitions_in_quality_order(
    repos: tuple[TrackRepository, TransitionRepository, AsyncSession],
) -> None:
    track_repo, trans_repo, session = repos
    a = await track_repo.create(title="A")
    b = await track_repo.create(title="B")
    c = await track_repo.create(title="C")
    d = await track_repo.create(title="D")
    # Three transitions FROM a — varying quality, plus one with NULL.
    session.add_all(
        [
            Transition(from_track_id=a.id, to_track_id=b.id, overall_quality=0.6),
            Transition(from_track_id=a.id, to_track_id=c.id, overall_quality=0.9),
            Transition(from_track_id=a.id, to_track_id=d.id, overall_quality=None),
            # Transition NOT from a — must be excluded.
            Transition(from_track_id=b.id, to_track_id=c.id, overall_quality=0.95),
        ]
    )
    await session.flush()

    rows = await trans_repo.list_from(a.id, limit=10)
    assert [r.to_track_id for r in rows] == [c.id, b.id, d.id]
    # b->c excluded — wrong from_track_id.
    assert all(r.from_track_id == a.id for r in rows)


@pytest.mark.asyncio
async def test_list_from_respects_limit(
    repos: tuple[TrackRepository, TransitionRepository, AsyncSession],
) -> None:
    track_repo, trans_repo, session = repos
    a = await track_repo.create(title="A")
    targets = [await track_repo.create(title=f"T{i}") for i in range(5)]
    for i, t in enumerate(targets):
        session.add(Transition(from_track_id=a.id, to_track_id=t.id, overall_quality=0.1 * i))
    await session.flush()

    rows = await trans_repo.list_from(a.id, limit=2)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_list_from_empty_for_track_with_no_transitions(
    repos: tuple[TrackRepository, TransitionRepository, AsyncSession],
) -> None:
    track_repo, trans_repo, _ = repos
    a = await track_repo.create(title="solo")
    rows = await trans_repo.list_from(a.id)
    assert rows == []


@pytest.mark.asyncio
async def test_search_by_bpm_range_returns_in_window(
    repos: tuple[TrackRepository, TransitionRepository, AsyncSession],
) -> None:
    track_repo, _, session = repos
    targets = []
    for i, bpm in enumerate([118.0, 124.0, 128.0, 132.0]):
        t = await track_repo.create(title=f"T{i}")
        session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=bpm))
        targets.append(t)
    await session.flush()

    found = await track_repo.search_by_bpm_range(bpm_min=120.0, bpm_max=130.0)
    titles = sorted(t.title for t in found)
    # Only the 124 and 128 BPM tracks fall in [120,130].
    assert titles == ["T1", "T2"]


@pytest.mark.asyncio
async def test_search_by_bpm_range_excludes_ids(
    repos: tuple[TrackRepository, TransitionRepository, AsyncSession],
) -> None:
    track_repo, _, session = repos
    a = await track_repo.create(title="A")
    b = await track_repo.create(title="B")
    session.add_all(
        [
            TrackAudioFeaturesComputed(track_id=a.id, bpm=125.0),
            TrackAudioFeaturesComputed(track_id=b.id, bpm=125.0),
        ]
    )
    await session.flush()

    found = await track_repo.search_by_bpm_range(bpm_min=120.0, bpm_max=130.0, exclude_ids={a.id})
    assert {t.id for t in found} == {b.id}


@pytest.mark.asyncio
async def test_search_by_bpm_range_skips_archived(
    repos: tuple[TrackRepository, TransitionRepository, AsyncSession],
) -> None:
    track_repo, _, session = repos
    active = await track_repo.create(title="active")  # status defaults to 0
    archived = await track_repo.create(title="archived", status=1)
    session.add_all(
        [
            TrackAudioFeaturesComputed(track_id=active.id, bpm=125.0),
            TrackAudioFeaturesComputed(track_id=archived.id, bpm=125.0),
        ]
    )
    await session.flush()

    found = await track_repo.search_by_bpm_range(bpm_min=120.0, bpm_max=130.0)
    assert {t.id for t in found} == {active.id}


@pytest.mark.asyncio
async def test_search_by_bpm_range_skips_tracks_without_features(
    repos: tuple[TrackRepository, TransitionRepository, AsyncSession],
) -> None:
    track_repo, _, session = repos
    with_feat = await track_repo.create(title="W")
    without_feat = await track_repo.create(title="X")  # no features row at all
    session.add(TrackAudioFeaturesComputed(track_id=with_feat.id, bpm=125.0))
    await session.flush()

    found = await track_repo.search_by_bpm_range(bpm_min=120.0, bpm_max=130.0)
    assert {t.id for t in found} == {with_feat.id}
    assert without_feat.id not in {t.id for t in found}
