from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.multi_deck.compatibility import compute_stem_compatibility
from app.domain.multi_deck.models import StemLayer


@pytest.mark.asyncio
async def test_two_compatible_stems():
    mock_stem_a = MagicMock(
        track_id=1, stem_name="drums",
        bpm=135.0, key_code=7,
        energy_sub=0.3, energy_low=0.4, energy_lowmid=0.3,
        energy_mid=0.2, energy_highmid=0.1, energy_high=0.05,
    )
    mock_stem_b = MagicMock(
        track_id=2, stem_name="bass",
        bpm=134.8, key_code=7,
        energy_sub=0.2, energy_low=0.5, energy_lowmid=0.3,
        energy_mid=0.1, energy_highmid=0.05, energy_high=0.02,
    )
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(
        side_effect=lambda tid: [mock_stem_a] if tid == 1 else [mock_stem_b]
    )

    result = await compute_stem_compatibility(uow, [
        StemLayer(track_id=1, stem_name="drums"),
        StemLayer(track_id=2, stem_name="bass"),
    ])
    assert not result.hard_reject
    assert result.overall_score > 0.5


@pytest.mark.asyncio
async def test_clash_detection():
    mock_a = MagicMock(
        track_id=1, stem_name="drums",
        bpm=135.0, key_code=7,
        energy_sub=0.8, energy_low=0.9, energy_lowmid=0.3,
        energy_mid=0.2, energy_highmid=0.1, energy_high=0.05,
    )
    mock_b = MagicMock(
        track_id=2, stem_name="bass",
        bpm=135.0, key_code=7,
        energy_sub=0.2, energy_low=0.85, energy_lowmid=0.3,
        energy_mid=0.1, energy_highmid=0.05, energy_high=0.02,
    )
    uow = MagicMock()
    uow.stem_features.get_all_for_track = AsyncMock(
        side_effect=lambda tid: [mock_a] if tid == 1 else [mock_b]
    )

    result = await compute_stem_compatibility(uow, [
        StemLayer(track_id=1, stem_name="drums"),
        StemLayer(track_id=2, stem_name="bass"),
    ])
    assert result.per_band["low"].clash
    assert len(result.recommendations) >= 1


@pytest.mark.asyncio
async def test_single_stem():
    uow = MagicMock()
    result = await compute_stem_compatibility(uow, [
        StemLayer(track_id=1, stem_name="drums"),
    ])
    assert result.overall_score == 1.0
    assert not result.hard_reject
