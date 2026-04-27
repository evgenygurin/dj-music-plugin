"""Audit iter 43 (T-41): ``local://tracks/{id}/suggest_next?energy_direction=up|down``
was a no-op — the filter compared candidate ``energy_mean`` against
absolute thresholds (``<= 0`` for "up", ``>= 1`` for "down"). Real
``energy_mean`` always falls in (0, 1) for techno, so neither
threshold ever fired. The directional knob did nothing.

Live confirmation before fix:

    /suggest_next?limit=5&energy_direction=down
    -> same 5 candidates as no-filter call

Fix: compare candidate energy against the SOURCE track's energy.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.track import track_suggest_next
from app.shared.features import TrackFeatures


def _row(to_track_id: int, quality: float = 0.7) -> MagicMock:
    r = MagicMock()
    r.to_track_id = to_track_id
    r.overall_quality = quality
    return r


@pytest.mark.asyncio
async def test_energy_direction_up_filters_lower_energy_candidates() -> None:
    """source.energy_mean=0.5 + direction=up → drop candidates ≤ 0.5."""
    rows = [_row(101), _row(102), _row(103)]
    feats = {
        # source
        42: TrackFeatures(energy_mean=0.5),
        # candidates
        101: TrackFeatures(energy_mean=0.7),  # higher → kept
        102: TrackFeatures(energy_mean=0.3),  # lower → filtered
        103: TrackFeatures(energy_mean=0.9),  # higher → kept
    }
    uow = MagicMock()
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(side_effect=lambda tid: MagicMock(id=tid, title=f"T{tid}"))
    uow.transitions = MagicMock()
    uow.transitions.list_from = AsyncMock(return_value=rows)
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)

    payload = json.loads(await track_suggest_next(id=42, limit=10, energy_direction="up", uow=uow))
    ids = [c["track_id"] for c in payload["candidates"]]
    assert 101 in ids and 103 in ids
    assert 102 not in ids


@pytest.mark.asyncio
async def test_energy_direction_down_filters_higher_energy_candidates() -> None:
    """source.energy_mean=0.5 + direction=down → drop candidates ≥ 0.5."""
    rows = [_row(201), _row(202), _row(203)]
    feats = {
        42: TrackFeatures(energy_mean=0.5),
        201: TrackFeatures(energy_mean=0.3),  # lower → kept
        202: TrackFeatures(energy_mean=0.7),  # higher → filtered
        203: TrackFeatures(energy_mean=0.5),  # equal → filtered (>=)
    }
    uow = MagicMock()
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(side_effect=lambda tid: MagicMock(id=tid, title=f"T{tid}"))
    uow.transitions = MagicMock()
    uow.transitions.list_from = AsyncMock(return_value=rows)
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)

    payload = json.loads(
        await track_suggest_next(id=42, limit=10, energy_direction="down", uow=uow)
    )
    ids = [c["track_id"] for c in payload["candidates"]]
    assert ids == [201]


@pytest.mark.asyncio
async def test_no_direction_filter_passes_all() -> None:
    """No direction → all candidates pass through."""
    rows = [_row(301), _row(302)]
    feats = {
        301: TrackFeatures(energy_mean=0.3),
        302: TrackFeatures(energy_mean=0.9),
    }
    uow = MagicMock()
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(side_effect=lambda tid: MagicMock(id=tid, title=f"T{tid}"))
    uow.transitions = MagicMock()
    uow.transitions.list_from = AsyncMock(return_value=rows)
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)

    payload = json.loads(await track_suggest_next(id=42, limit=10, energy_direction=None, uow=uow))
    assert {c["track_id"] for c in payload["candidates"]} == {301, 302}


@pytest.mark.asyncio
async def test_all_filtered_returns_explicit_reason() -> None:
    """If every candidate gets filtered, ``reason`` explains why."""
    rows = [_row(401), _row(402)]
    feats = {
        42: TrackFeatures(energy_mean=0.5),
        401: TrackFeatures(energy_mean=0.2),  # lower than 0.5
        402: TrackFeatures(energy_mean=0.1),  # lower than 0.5
    }
    uow = MagicMock()
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(side_effect=lambda tid: MagicMock(id=tid, title=f"T{tid}"))
    uow.transitions = MagicMock()
    uow.transitions.list_from = AsyncMock(return_value=rows)
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)

    payload = json.loads(await track_suggest_next(id=42, limit=10, energy_direction="up", uow=uow))
    assert payload["candidates"] == []
    assert "energy_direction" in (payload["reason"] or "")
