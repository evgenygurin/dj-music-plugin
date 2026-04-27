"""Audit iter 42 (T-40): ``local://tracks/{id}/suggest_replacement``
returned ``score=0.0`` for every candidate, regardless of how
compatible it actually was. Live confirmation:

    [{"track_id":207,"score":0,...},
     {"track_id":208,"score":0,...},
     ...]

The hardcoded zero made the resource useless for ranking — caller
couldn't tell which candidate was the best replacement. Now we
score each candidate against the surrounding set track using
``TransitionScorer`` and sort best-first.

Anchor selection:
* ``position - 1`` if it exists (candidate mixes INTO predecessor)
* else ``position + 1`` (candidate mixes OUT to successor)
* else no anchor (single-track set) — ``score=0.0`` honestly,
  with a reason string explaining why.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.track import track_suggest_replacement
from app.shared.features import TrackFeatures


def _features(bpm: float = 128.0, key: int = 8, lufs: float = -10.0) -> TrackFeatures:
    return TrackFeatures(
        bpm=bpm,
        key_code=key,
        integrated_lufs=lufs,
        energy_mean=0.5,
        kick_prominence=0.3,
        hp_ratio=0.4,
        spectral_centroid_hz=2000.0,
        spectral_flatness=0.1,
        onset_rate=2.0,
        hnr_db=10.0,
        chroma_entropy=0.5,
    )


def _set_item(track_id: int, sort_index: int) -> MagicMock:
    item = MagicMock()
    item.track_id = track_id
    item.sort_index = sort_index
    return item


def _track(track_id: int, title: str) -> MagicMock:
    t = MagicMock()
    t.id = track_id
    t.title = title
    return t


@pytest.mark.asyncio
async def test_score_uses_predecessor_anchor() -> None:
    """``position - 1`` exists → score against predecessor."""
    # Set has [pos 0=track 1, pos 1=removed track 50, pos 2=track 3].
    # Replacing pos 1 → anchor on pos 0 (track 1).
    items = [_set_item(1, 0), _set_item(50, 1), _set_item(3, 2)]
    candidates = [_track(100, "Cand"), _track(200, "Cand2")]

    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=MagicMock(id=1))
    uow.set_versions = MagicMock()
    uow.set_versions.latest_version = AsyncMock(return_value=MagicMock(id=99))
    uow.set_versions.get_items = AsyncMock(return_value=items)
    uow.track_features = MagicMock()
    # removed track features (BPM 128) — drives the BPM window.
    uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=[
            {50: _features(bpm=128.0)},  # first call: removed track
            {  # second call: candidates + anchor
                100: _features(bpm=128.5),
                200: _features(bpm=130.0),
                1: _features(bpm=128.0, key=8),  # anchor (predecessor)
            },
        ]
    )
    uow.tracks = MagicMock()
    uow.tracks.search_by_bpm_range = AsyncMock(return_value=candidates)

    payload = json.loads(await track_suggest_replacement(id=50, set_id=1, position=1, uow=uow))
    assert payload["candidates"]
    # Every score now non-zero (real TransitionScorer output)
    for cand in payload["candidates"]:
        assert cand["score"] > 0, cand
    # Sorted best-first.
    scores = [c["score"] for c in payload["candidates"]]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_score_uses_successor_when_no_predecessor() -> None:
    """``position == 0`` → fall back to successor anchor."""
    items = [_set_item(50, 0), _set_item(2, 1)]  # removed at pos 0
    candidates = [_track(100, "Cand")]

    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=MagicMock(id=1))
    uow.set_versions = MagicMock()
    uow.set_versions.latest_version = AsyncMock(return_value=MagicMock(id=99))
    uow.set_versions.get_items = AsyncMock(return_value=items)
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=[
            {50: _features(bpm=128.0)},
            {100: _features(bpm=128.5), 2: _features(bpm=128.0)},
        ]
    )
    uow.tracks = MagicMock()
    uow.tracks.search_by_bpm_range = AsyncMock(return_value=candidates)

    payload = json.loads(await track_suggest_replacement(id=50, set_id=1, position=0, uow=uow))
    assert len(payload["candidates"]) == 1
    assert payload["candidates"][0]["score"] > 0


@pytest.mark.asyncio
async def test_no_anchor_when_single_track_set() -> None:
    """Single-track set → no anchor → score=0 with explicit reason."""
    items = [_set_item(50, 0)]  # only the removed track
    candidates = [_track(100, "Cand")]

    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=MagicMock(id=1))
    uow.set_versions = MagicMock()
    uow.set_versions.latest_version = AsyncMock(return_value=MagicMock(id=99))
    uow.set_versions.get_items = AsyncMock(return_value=items)
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(
        side_effect=[
            {50: _features(bpm=128.0)},
            {100: _features(bpm=128.5)},
        ]
    )
    uow.tracks = MagicMock()
    uow.tracks.search_by_bpm_range = AsyncMock(return_value=candidates)

    payload = json.loads(await track_suggest_replacement(id=50, set_id=1, position=0, uow=uow))
    cand = payload["candidates"][0]
    assert cand["score"] == 0.0
    assert "no anchor" in cand["reason"]
