from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.multi_deck.energy_budget import compute_energy_budget
from app.domain.multi_deck.models import StemLayer


@pytest.mark.asyncio
async def test_energy_budget():
    mock_a = MagicMock(
        stem_name="drums",
        integrated_lufs=-10.0,
        energy_sub=0.3,
        energy_low=0.4,
        energy_lowmid=0.3,
        energy_mid=0.2,
        energy_highmid=0.1,
        energy_high=0.05,
    )
    mock_b = MagicMock(
        stem_name="bass",
        integrated_lufs=-12.0,
        energy_sub=0.1,
        energy_low=0.3,
        energy_lowmid=0.2,
        energy_mid=0.1,
        energy_highmid=0.05,
        energy_high=0.02,
    )
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(
        side_effect=lambda tid: [mock_a] if tid == 1 else [mock_b]
    )

    result = await compute_energy_budget(
        uow,
        [
            StemLayer(track_id=1, stem_name="drums"),
            StemLayer(track_id=2, stem_name="bass"),
        ],
        target_lufs=-8.0,
    )

    assert result.total_lufs < -8.0
    assert result.headroom_db > 0


@pytest.mark.asyncio
async def test_energy_budget_with_gain():
    mock_a = MagicMock(
        stem_name="drums",
        integrated_lufs=-10.0,
        energy_sub=0.5,
        energy_low=0.5,
        energy_lowmid=0.5,
        energy_mid=0.5,
        energy_highmid=0.5,
        energy_high=0.5,
    )
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(return_value=[mock_a])

    result = await compute_energy_budget(
        uow,
        [StemLayer(track_id=1, stem_name="drums")],
        gain_db=[6.0],
        target_lufs=-8.0,
    )

    assert result.total_lufs < -2.0


@pytest.mark.asyncio
async def test_energy_budget_missing_features():
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(return_value=[])

    result = await compute_energy_budget(
        uow,
        [StemLayer(track_id=1, stem_name="missing")],
        target_lufs=-8.0,
    )

    assert result.total_lufs == 0.0
    assert result.headroom_db == -8.0
    # When no features found, all bands show as overloaded (0 > target_lufs)
    all_bands = set(result.per_band.keys())
    assert all_bands == {"sub", "low", "lowmid", "mid", "highmid", "high"}


@pytest.mark.asyncio
async def test_energy_budget_band_overload():
    mock_a = MagicMock(
        stem_name="drums",
        integrated_lufs=-5.0,
        energy_sub=10.0,
        energy_low=0.1,
        energy_lowmid=0.1,
        energy_mid=0.1,
        energy_highmid=0.1,
        energy_high=0.1,
    )
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(return_value=[mock_a])

    result = await compute_energy_budget(
        uow,
        [StemLayer(track_id=1, stem_name="drums")],
        target_lufs=-8.0,
    )

    assert result.per_band["sub"].warning is True
    assert "sub band overloaded" in result.recommendation
