from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.domain.multi_deck.bpm_ratio import analyze_bpm_ratio


@pytest.mark.asyncio
async def test_bpm_ratio_3to4():
    uow = MagicMock()
    result = await analyze_bpm_ratio(uow, 135.0)
    labels = {m.ratio_label for m in result.matches}
    assert "4:3" in labels
    assert "3:4" in labels

    match_34 = [m for m in result.matches if m.ratio_label == "3:4"]
    assert len(match_34) >= 1
    assert abs(match_34[0].bpm_b - 101.25) < 0.5


@pytest.mark.asyncio
async def test_bpm_ratio_range_respected():
    uow = MagicMock()
    result = await analyze_bpm_ratio(uow, 60.0, bpm_range=(100, 200))
    for m in result.matches:
        assert 100 <= m.bpm_b <= 200


@pytest.mark.asyncio
async def test_bpm_ratio_filtered():
    uow = MagicMock()
    result = await analyze_bpm_ratio(uow, 120.0, ratios_of_interest=["3:4", "2:3"])
    labels = {m.ratio_label for m in result.matches}
    assert labels <= {"3:4", "2:3"}


@pytest.mark.asyncio
async def test_bpm_ratio_bars_alignment():
    uow = MagicMock()
    result = await analyze_bpm_ratio(uow, 128.0, ratios_of_interest=["3:4"])
    assert len(result.matches) >= 1
    m = result.matches[0]
    assert m.bars_to_align >= 1
    assert m.seconds_to_align > 0
    assert m.ratio_label == "3:4"


@pytest.mark.asyncio
async def test_bpm_ratio_unknown_label_ignored():
    uow = MagicMock()
    result = await analyze_bpm_ratio(uow, 120.0, ratios_of_interest=["7:8"])
    assert len(result.matches) == 0
