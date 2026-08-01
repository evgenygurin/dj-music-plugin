from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.features import TrackFeatures
from app.tools.compute.sequence_optimize import sequence_optimize


def _uow_with_features(feats: dict[int, TrackFeatures]) -> MagicMock:
    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)
    return uow


def _peak_time_pool() -> dict[int, TrackFeatures]:
    energies = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    return {
        100 + i: TrackFeatures(bpm=130.0, energy_mean=e, key_code=None, integrated_lufs=-12.0)
        for i, e in enumerate(energies)
    }


@pytest.mark.asyncio
async def test_energy_arc_peak_time_returns_arc_order() -> None:
    out = await sequence_optimize(
        track_ids=[100, 101, 102, 103, 104, 105],
        energy_arc="peak_time",
        uow=_uow_with_features(_peak_time_pool()),
        scorer=MagicMock(),
        optimizer_builder=MagicMock(),
    )
    assert out.algorithm == "peak_time"
    pool = _peak_time_pool()
    ordered = [pool[tid].energy_mean for tid in out.track_order]
    # peak (0.75) lands near the end but not last
    peak_idx = ordered.index(max(ordered))
    assert peak_idx >= len(ordered) - 2
    assert peak_idx < len(ordered) - 1
    assert ordered[-1] < max(ordered)


@pytest.mark.asyncio
async def test_energy_arc_peak_time_respects_excluded() -> None:
    out = await sequence_optimize(
        track_ids=[100, 101, 102, 103, 104, 105],
        energy_arc="peak_time",
        excluded=[104],
        uow=_uow_with_features(_peak_time_pool()),
        scorer=MagicMock(),
        optimizer_builder=MagicMock(),
    )
    assert 104 not in out.track_order
    assert len(out.track_order) == 5
