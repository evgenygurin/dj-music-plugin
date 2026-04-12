"""Tests for TransitionHistoryRepository."""

import pytest

from dj_music.models.track import Track
from dj_music.models.transition_history import TransitionHistory
from dj_music.repositories.transition_history import TransitionHistoryRepository


@pytest.fixture
def repo(db):
    return TransitionHistoryRepository(db)


async def _seed_tracks(session, count=3):
    tracks = [Track(title=f"Track {i}", status=0) for i in range(count)]
    session.add_all(tracks)
    await session.flush()
    return tracks


@pytest.mark.asyncio
async def test_log_and_retrieve(repo, db):
    tracks = await _seed_tracks(db)
    entry = TransitionHistory(
        from_track_id=tracks[0].id,
        to_track_id=tracks[1].id,
        overall_score=0.85,
        style="swap",
        session_id="test-session-1",
    )
    saved = await repo.log(entry)
    assert saved.id is not None
    assert saved.overall_score == 0.85
    history = await repo.get_history(from_track_id=tracks[0].id, limit=10)
    assert len(history) == 1
    assert history[0].to_track_id == tracks[1].id


@pytest.mark.asyncio
async def test_best_pairs(repo, db):
    tracks = await _seed_tracks(db, 4)
    for i, (to_idx, score, reaction) in enumerate(
        [
            (1, 0.9, "like"),
            (2, 0.7, "listened"),
            (3, 0.3, "ban"),
        ]
    ):
        entry = TransitionHistory(
            from_track_id=tracks[0].id,
            to_track_id=tracks[to_idx].id,
            overall_score=score,
            user_reaction=reaction,
            session_id=f"s{i}",
        )
        await repo.log(entry)
    pairs = await repo.get_best_pairs(tracks[0].id, limit=10)
    assert len(pairs) >= 2
    assert pairs[0]["track_id"] == tracks[1].id


@pytest.mark.asyncio
async def test_update_reaction(repo, db):
    tracks = await _seed_tracks(db)
    entry = TransitionHistory(
        from_track_id=tracks[0].id,
        to_track_id=tracks[1].id,
        overall_score=0.8,
        session_id="s1",
    )
    saved = await repo.log(entry)
    await repo.update_reaction(saved.id, "like")
    await db.flush()
    refreshed = await repo.get_by_id(saved.id)
    assert refreshed.user_reaction == "like"
