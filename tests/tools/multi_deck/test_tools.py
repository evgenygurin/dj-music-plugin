from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_stem_vertical_compatibility_tool():
    from app.tools.multi_deck.compatibility import stem_vertical_compatibility

    with patch("app.tools.multi_deck.compatibility.compute_stem_compatibility") as mock:
        mock.return_value = MagicMock(
            overall_score=0.8, hard_reject=False,
            per_band={},
            key_compatibility={"score": 0.9},
            bpm_compatibility={"score": 0.9},
            recommendations=[],
        )
        uow = MagicMock()
        result = await stem_vertical_compatibility(
            layers=[{"track_id": 1, "stem_name": "drums"}],
            uow=uow,
        )
        assert result["overall_score"] == 0.8


@pytest.mark.asyncio
async def test_energy_budget_tool():
    from app.tools.multi_deck.energy_budget import energy_budget

    with patch("app.tools.multi_deck.energy_budget.compute_energy_budget") as mock:
        mock.return_value = MagicMock(
            total_lufs=-10.0, headroom_db=2.0,
            per_band={},
            recommendation="OK",
        )
        uow = MagicMock()
        result = await energy_budget(
            layers=[{"track_id": 1, "stem_name": "drums"}],
            uow=uow,
        )
        assert result["total_lufs"] == -10.0


@pytest.mark.asyncio
async def test_all_tools_registered():
    import app.tools.multi_deck.bpm_ratio
    import app.tools.multi_deck.compatibility
    import app.tools.multi_deck.energy_budget
    import app.tools.multi_deck.stem_embedding
    import app.tools.multi_deck.timeline  # noqa: F401
