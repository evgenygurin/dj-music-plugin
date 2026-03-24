"""Tests for Transition and TransitionCandidate models."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.track import Track
from app.models.transition import Transition, TransitionCandidate


async def _make_track(db, title: str = "Test Track") -> Track:
    t = Track(title=title)
    db.add(t)
    await db.flush()
    return t


async def test_create_transition(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "From")
    t2 = await _make_track(db, "To")

    tr = Transition(from_track_id=t1.id, to_track_id=t2.id)
    db.add(tr)
    await db.flush()
    assert tr.id is not None
    assert tr.from_track_id == t1.id
    assert tr.to_track_id == t2.id


async def test_transition_with_scores(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    tr = Transition(
        from_track_id=t1.id,
        to_track_id=t2.id,
        overlap_ms=16000,
        bpm_score=0.95,
        energy_score=0.8,
        harmonic_score=0.7,
        spectral_score=0.6,
        groove_score=0.5,
        key_distance_weighted=0.9,
        low_conflict_score=0.85,
        overall_quality=0.78,
    )
    db.add(tr)
    await db.flush()
    assert tr.overall_quality == 0.78
    assert tr.bpm_score == 0.95


async def test_transition_score_zero(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    tr = Transition(from_track_id=t1.id, to_track_id=t2.id, bpm_score=0.0)
    db.add(tr)
    await db.flush()
    assert tr.bpm_score == 0.0


async def test_transition_score_one(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    tr = Transition(from_track_id=t1.id, to_track_id=t2.id, overall_quality=1.0)
    db.add(tr)
    await db.flush()
    assert tr.overall_quality == 1.0


async def test_transition_score_out_of_range(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    tr = Transition(from_track_id=t1.id, to_track_id=t2.id, bpm_score=1.5)
    db.add(tr)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_transition_score_negative(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    tr = Transition(from_track_id=t1.id, to_track_id=t2.id, energy_score=-0.1)
    db.add(tr)
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_transition_unique_constraint(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    db.add(Transition(from_track_id=t1.id, to_track_id=t2.id))
    await db.flush()

    db.add(Transition(from_track_id=t1.id, to_track_id=t2.id))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_create_transition_candidate(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    tc = TransitionCandidate(
        from_track_id=t1.id,
        to_track_id=t2.id,
        bpm_distance=2.5,
        key_distance=1,
        embedding_similarity=0.92,
        energy_delta=0.15,
    )
    db.add(tc)
    await db.flush()
    assert tc.id is not None
    assert tc.fully_scored is False


async def test_transition_candidate_fully_scored(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    tc = TransitionCandidate(from_track_id=t1.id, to_track_id=t2.id, fully_scored=True)
    db.add(tc)
    await db.flush()
    assert tc.fully_scored is True


async def test_transition_candidate_unique(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    db.add(TransitionCandidate(from_track_id=t1.id, to_track_id=t2.id))
    await db.flush()

    db.add(TransitionCandidate(from_track_id=t1.id, to_track_id=t2.id))
    with pytest.raises(IntegrityError):
        await db.flush()


async def test_transition_timestamps(db):  # type: ignore[no-untyped-def]
    t1 = await _make_track(db, "A")
    t2 = await _make_track(db, "B")

    tr = Transition(from_track_id=t1.id, to_track_id=t2.id)
    db.add(tr)
    await db.flush()
    assert tr.created_at is not None
    assert tr.updated_at is not None
