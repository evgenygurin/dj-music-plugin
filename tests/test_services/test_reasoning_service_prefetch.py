"""Tests for ReasoningService — suggest_next_track refactor.

Covers:
- Batch track fetch replaces N+1 get_by_id calls
- Speculative prefetch wired: triggers PrefetchService exactly once
- Prefetch summary attached to response when enabled
- Prefetch disabled → no call when settings.prefetch_on_suggest is False
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.core.config import settings
from dj_music.models.audio import TrackAudioFeaturesComputed
from dj_music.models.playlist import Playlist, PlaylistItem
from dj_music.models.set import DjSet, SetItem, SetVersion
from dj_music.models.track import Track
from dj_music.repositories.feature import FeatureRepository
from dj_music.repositories.playlist import PlaylistRepository
from dj_music.repositories.set import SetRepository
from dj_music.repositories.track import TrackRepository
from dj_music.repositories.transition import TransitionRepository
from dj_music.services.prefetch_service import PrefetchResult
from dj_music.services.reasoning_service import ReasoningService


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


async def _seed_set_with_playlist(
    db: AsyncSession,
    set_size: int = 2,
    pool_size: int = 5,
) -> tuple[int, list[int]]:
    """Build a set with ``set_size`` tracks pulling from a playlist of
    ``set_size + pool_size`` tracks.

    Returns ``(set_id, extra_pool_ids)``. Every track has features.
    """
    playlist = Playlist(name="Pool")
    db.add(playlist)
    await db.flush()

    set_track_ids: list[int] = []
    for i in range(set_size):
        t = Track(title=f"Set {i + 1}", duration_ms=300_000, status=0)
        db.add(t)
        await db.flush()
        db.add(PlaylistItem(playlist_id=playlist.id, track_id=t.id, sort_index=i))
        db.add(_features(t.id, bpm=128.0 + i * 0.5))
        set_track_ids.append(t.id)

    extra_ids: list[int] = []
    for i in range(pool_size):
        t = Track(title=f"Pool {i + 1}", duration_ms=300_000, status=0)
        db.add(t)
        await db.flush()
        db.add(PlaylistItem(playlist_id=playlist.id, track_id=t.id, sort_index=set_size + i))
        db.add(_features(t.id, bpm=128.0 + (i + set_size) * 0.5))
        extra_ids.append(t.id)

    dj_set = DjSet(name="S", source_playlist_id=playlist.id)
    db.add(dj_set)
    await db.flush()
    version = SetVersion(set_id=dj_set.id, label="v1")
    db.add(version)
    await db.flush()
    for i, tid in enumerate(set_track_ids):
        db.add(SetItem(version_id=version.id, track_id=tid, sort_index=i))
    await db.flush()
    return dj_set.id, extra_ids


def _make_svc(
    db: AsyncSession,
    prefetch_mock: Any = None,
) -> ReasoningService:
    return ReasoningService(
        set_repo=SetRepository(db),
        track_repo=TrackRepository(db),
        playlist_repo=PlaylistRepository(db),
        feature_repo=FeatureRepository(db),
        transition_repo=TransitionRepository(db),
        prefetch_service=prefetch_mock,
    )


@pytest.mark.asyncio
async def test_suggest_next_track_returns_sorted_candidates(db: AsyncSession) -> None:
    set_id, extras = await _seed_set_with_playlist(db, set_size=2, pool_size=4)
    svc = _make_svc(db, prefetch_mock=None)

    response = await svc.suggest_next_track(set_id=set_id, after_position=1, count=3)

    assert response["set_id"] == set_id
    assert len(response["suggestions"]) <= 3
    scores = [s["score"] for s in response["suggestions"]]
    assert scores == sorted(scores, reverse=True)
    returned_ids = {s["track_id"] for s in response["suggestions"]}
    assert returned_ids.issubset(set(extras))


@pytest.mark.asyncio
async def test_suggest_next_track_triggers_prefetch_when_enabled(
    db: AsyncSession,
) -> None:
    """When prefetch_on_suggest is True, top suggestion drives prefetch once."""
    set_id, extras = await _seed_set_with_playlist(db, set_size=2, pool_size=4)

    mock_result = PrefetchResult(
        seed_track_id=extras[0],
        candidates_considered=3,
        pairs_scored=3,
        pairs_cached_hit=0,
        analysis_scheduled=0,
        analysis_skipped=0,
        hard_rejects=0,
        top_candidate_ids=extras[1:],
    )
    prefetch = MagicMock()
    prefetch.prefetch_after = AsyncMock(return_value=mock_result)

    svc = _make_svc(db, prefetch_mock=prefetch)

    original = settings.prefetch_on_suggest
    settings.prefetch_on_suggest = True
    try:
        response = await svc.suggest_next_track(set_id=set_id, after_position=1, count=3)
    finally:
        settings.prefetch_on_suggest = original

    assert prefetch.prefetch_after.await_count == 1
    called_with_seed = prefetch.prefetch_after.await_args.args[0]
    assert called_with_seed == int(response["suggestions"][0]["track_id"])
    assert "prefetch" in response
    assert response["prefetch"]["pairs_scored"] == 3


@pytest.mark.asyncio
async def test_suggest_next_track_prefetch_disabled(db: AsyncSession) -> None:
    """When prefetch_on_suggest is False, no prefetch is invoked."""
    set_id, _ = await _seed_set_with_playlist(db, set_size=2, pool_size=3)

    prefetch = MagicMock()
    prefetch.prefetch_after = AsyncMock()

    svc = _make_svc(db, prefetch_mock=prefetch)

    original = settings.prefetch_on_suggest
    settings.prefetch_on_suggest = False
    try:
        response = await svc.suggest_next_track(set_id=set_id, after_position=1, count=3)
    finally:
        settings.prefetch_on_suggest = original

    prefetch.prefetch_after.assert_not_called()
    assert "prefetch" not in response
