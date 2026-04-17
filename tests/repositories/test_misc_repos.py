"""Smoke-test every non-track repository: CRUD on its primary model."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, Track
from app.repositories.audio_file import AudioFileRepository
from app.repositories.key import KeyEdgeRepository, KeyRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.provider_metadata import (
    ProviderMetadataRepository,
    YandexMetadataRepository,
)
from app.repositories.scoring_profile import ScoringProfileRepository
from app.repositories.set import SetRepository, SetVersionRepository
from app.repositories.track_affinity import TrackAffinityRepository
from app.repositories.track_feedback import TrackFeedbackRepository
from app.repositories.transition import TransitionRepository
from app.repositories.transition_history import TransitionHistoryRepository


@pytest_asyncio.fixture
async def setup(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_playlist_append_and_get_ids(setup: None, session: AsyncSession) -> None:
    t = Track(title="x")
    session.add(t)
    await session.flush()
    repo = PlaylistRepository(session)
    pl = await repo.create(name="P")
    added = await repo.append_tracks(pl.id, [t.id])
    assert added == 1
    ids = await repo.get_track_ids(pl.id)
    assert ids == [t.id]


@pytest.mark.asyncio
async def test_set_version_roundtrip(setup: None, session: AsyncSession) -> None:
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    set_repo = SetRepository(session)
    sv_repo = SetVersionRepository(session)
    s = await set_repo.create(name="set")
    v = await sv_repo.create(set_id=s.id, version_label="v1", quality_score=0.7)
    n = await sv_repo.create_items(v.id, [t1.id, t2.id])
    assert n == 2
    items = await sv_repo.get_items(v.id)
    assert [i.track_id for i in items] == [t1.id, t2.id]


@pytest.mark.asyncio
async def test_audio_file_and_beatgrid(setup: None, session: AsyncSession) -> None:
    t = Track(title="x")
    session.add(t)
    await session.flush()
    repo = AudioFileRepository(session)
    f = await repo.create(track_id=t.id, file_path="/a.mp3", file_size=1, mime_type="audio/mpeg")
    bg = await repo.register_beatgrid(f.id, bpm=128.0, first_downbeat_ms=320.0, canonical=True)
    assert bg.id is not None


@pytest.mark.asyncio
async def test_transition_pair(setup: None, session: AsyncSession) -> None:
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    repo = TransitionRepository(session)
    await repo.create(from_track_id=t1.id, to_track_id=t2.id, overall_score=0.8)
    tr = await repo.get_pair(t1.id, t2.id)
    assert tr is not None
    assert tr.overall_score == 0.8


@pytest.mark.asyncio
async def test_history_best_pairs(setup: None, session: AsyncSession) -> None:
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    repo = TransitionHistoryRepository(session)
    await repo.create(from_track_id=t1.id, to_track_id=t2.id, overall_score=0.9)
    rows = await repo.best_pairs(limit=5)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_feedback_list(setup: None, session: AsyncSession) -> None:
    t = Track(title="x")
    session.add(t)
    await session.flush()
    repo = TrackFeedbackRepository(session)
    await repo.create(track_id=t.id, kind="like")
    rows = await repo.list_by_kind("like")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_affinity_recommend(setup: None, session: AsyncSession) -> None:
    t1, t2 = Track(title="a"), Track(title="b")
    session.add_all([t1, t2])
    await session.flush()
    repo = TrackAffinityRepository(session)
    await repo.create(track_a_id=t1.id, track_b_id=t2.id, avg_score=0.75)
    recs = await repo.recommend(t1.id, limit=5)
    assert len(recs) == 1


@pytest.mark.asyncio
async def test_scoring_profile_by_name(setup: None, session: AsyncSession) -> None:
    repo = ScoringProfileRepository(session)
    await repo.create(
        name="x",
        bpm_weight=0.2,
        harmonic_weight=0.15,
        energy_weight=0.15,
        spectral_weight=0.2,
        groove_weight=0.15,
        timbral_weight=0.15,
    )
    found = await repo.get_by_name("x")
    assert found is not None


@pytest.mark.asyncio
async def test_provider_metadata_lookup(setup: None, session: AsyncSession) -> None:
    repo = ProviderMetadataRepository(session)
    await repo.create(code="yandex_music", display_name="Yandex Music")
    p = await repo.get_by_code("yandex_music")
    assert p is not None


@pytest.mark.asyncio
async def test_yandex_metadata_lookup(setup: None, session: AsyncSession) -> None:
    t = Track(title="x")
    session.add(t)
    await session.flush()
    repo = YandexMetadataRepository(session)
    await repo.create(track_id=t.id, yandex_track_id="12345")
    row = await repo.get_for_track(t.id)
    assert row is not None


@pytest.mark.asyncio
async def test_key_by_camelot(setup: None, session: AsyncSession) -> None:
    repo = KeyRepository(session)
    await repo.create(key_code=0, pitch_class=0, mode=0, name="C minor", camelot="5A")
    k = await repo.get_by_camelot("5A")
    assert k is not None

    edges = KeyEdgeRepository(session)
    assert await edges.edges_from(0) == []
