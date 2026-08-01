"""Combined Feature 2 + 3 integration: peak-time energy arc with soft Camelot."""

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


def _pool() -> dict[int, TrackFeatures]:
    energies = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    return {
        100 + i: TrackFeatures(bpm=130.0, energy_mean=e, key_code=None, integrated_lufs=-12.0)
        for i, e in enumerate(energies)
    }


@pytest.mark.asyncio
async def test_peak_time_arc_with_soft_camelot() -> None:
    out = await sequence_optimize(
        track_ids=[100, 101, 102, 103, 104, 105],
        energy_arc="peak_time",
        camelot_mode="soft",
        uow=_uow_with_features(_pool()),
        scorer=MagicMock(),
        optimizer_builder=MagicMock(),
    )
    assert out.algorithm == "peak_time"
    assert len(out.track_order) == 6
    assert set(out.track_order) == {100, 101, 102, 103, 104, 105}
    assert 0.0 <= out.quality_score <= 1.0
