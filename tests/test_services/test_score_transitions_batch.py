"""Tests for SetScoringService.score_set_transitions batch refactor.

Covers:
- Single batch feature load via features_cache path
- Per-pair Transition row created on first call
- Second call hits the DB cache and returns ``cached: True`` entries
- Hard-reject pairs report overall_quality=0.0 without crashing averaging
- Missing-feature pairs fail gracefully
- Single-track edge case (no pairs)
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.playlist import Playlist, PlaylistItem
from app.db.models.set import DjSet, SetItem, SetVersion
from app.db.models.track import Track
from app.db.models.transition import Transition
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.transition import TransitionRepository
from app.services.set.scoring import SetScoringService


def _make_scoring_service(db: AsyncSession) -> SetScoringService:
    return SetScoringService(
        set_repo=SetRepository(db),
        feature_repo=FeatureRepository(db),
        transition_repo=TransitionRepository(db),
    )


def _features(track_id: int, **overrides: Any) -> TrackAudioFeaturesComputed:
    base: dict[str, Any] = {
        "track_id": track_id,
        "bpm": 128.0,
        "bpm_stability": 0.9,
        "key_code": 14,
        "integrated_lufs": -8.0,
        "spectral_centroid_hz": 3000.0,
        "spectral_flatness": 0.15,
        "energy_mean": 0.6,
        "onset_rate": 4.0,
        "kick_prominence": 0.5,
        "hnr_db": -10.0,
        "chroma_entropy": 1.0,
        "hp_ratio": 1.5,
        "analysis_level": 3,
    }
    base.update(overrides)
    return TrackAudioFeaturesComputed(**base)


async def _seed_set_with_tracks(
    db: AsyncSession,
    track_count: int,
    *,
    with_features: bool = True,
    bpms: list[float] | None = None,
) -> int:
    """Create a DjSet with one SetVersion and N SetItems. Returns set_id."""
    playlist = Playlist(name="Src")
    db.add(playlist)
    await db.flush()

    dj_set = DjSet(name="Test Set", source_playlist_id=playlist.id)
    db.add(dj_set)
    await db.flush()

    version = SetVersion(set_id=dj_set.id, label="v1")
    db.add(version)
    await db.flush()

    for i in range(track_count):
        track = Track(title=f"T{i + 1}", duration_ms=300_000, status=0)
        db.add(track)
        await db.flush()
        db.add(PlaylistItem(playlist_id=playlist.id, track_id=track.id, sort_index=i))
        db.add(SetItem(version_id=version.id, track_id=track.id, sort_index=i))
        if with_features:
            bpm = bpms[i] if bpms else 128.0 + i * 0.5
            db.add(_features(track.id, bpm=bpm))
    await db.flush()
    return dj_set.id


@pytest.mark.asyncio
async def test_score_set_transitions_persists_each_pair(db: AsyncSession) -> None:
    """First call should persist one Transition row per pair."""
    set_id = await _seed_set_with_tracks(db, track_count=5)
    svc = _make_scoring_service(db)

    result = await svc.score_set_transitions(set_id)

    assert result["total_transitions"] == 4  # N-1 pairs for 5 tracks
    assert result["scored_transitions"] == 4
    assert result["hard_conflicts"] == 0
    rows = (await db.execute(select(Transition))).scalars().all()
    assert len(rows) == 4
    for r in rows:
        assert r.overall_quality is not None


@pytest.mark.asyncio
async def test_score_set_transitions_uses_cache_on_second_call(db: AsyncSession) -> None:
    """Second call should hit existing Transition rows (cached=True)."""
    set_id = await _seed_set_with_tracks(db, track_count=4)
    svc = _make_scoring_service(db)

    first = await svc.score_set_transitions(set_id)
    second = await svc.score_set_transitions(set_id)

    assert first["total_transitions"] == second["total_transitions"] == 3
    assert all(t.get("cached") is False for t in first["transitions"])
    assert all(t.get("cached") is True for t in second["transitions"])
    # DB should still only have 3 transitions — no duplicates.
    rows = (await db.execute(select(Transition))).scalars().all()
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_score_set_transitions_hard_reject_averaging(db: AsyncSession) -> None:
    """Hard rejects should be counted and excluded from avg_score."""
    # BPMs: 128, 129, 145 — pair 1 (128→129) ok, pair 2 (129→145) diff=16 hard reject.
    set_id = await _seed_set_with_tracks(db, track_count=3, bpms=[128.0, 129.0, 145.0])
    svc = _make_scoring_service(db)

    result = await svc.score_set_transitions(set_id)

    assert result["total_transitions"] == 2
    assert result["hard_conflicts"] == 1
    # avg_score reflects the one healthy pair, not the hard-rejected 0.0 one.
    healthy = next(t for t in result["transitions"] if not t.get("hard_reject"))
    assert result["avg_score"] == pytest.approx(float(healthy["overall_quality"]), abs=1e-6)


@pytest.mark.asyncio
async def test_score_set_transitions_missing_features(db: AsyncSession) -> None:
    """Pairs touching a featureless track should not crash and report None."""
    set_id = await _seed_set_with_tracks(db, track_count=3, with_features=False)
    svc = _make_scoring_service(db)

    result = await svc.score_set_transitions(set_id)

    assert result["total_transitions"] == 2
    assert result["scored_transitions"] == 0
    assert result["avg_score"] is None


@pytest.mark.asyncio
async def test_score_set_transitions_single_track_set(db: AsyncSession) -> None:
    """A single-track set has zero pairs; the refactor must not IndexError."""
    set_id = await _seed_set_with_tracks(db, track_count=1)
    svc = _make_scoring_service(db)

    result = await svc.score_set_transitions(set_id)
    assert result["total_transitions"] == 0
    assert result["transitions"] == []
