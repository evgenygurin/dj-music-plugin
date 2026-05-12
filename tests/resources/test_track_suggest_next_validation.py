"""Regression: validate ``energy_direction`` for the suggest_next resource.

Standalone (no ``client``/``seeded_db`` Phase 5 fixtures) — invokes the
resource function directly with a mocked UoW so it runs today.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.track import track_suggest_next
from app.shared.errors import ValidationError


@pytest.mark.asyncio
async def test_suggest_next_rejects_unknown_energy_direction() -> None:
    """Previously the @resource bound ``energy_direction`` as a raw
    ``str | None`` with no validation, so ``?energy_direction=sideways``
    fell through the ``direction in {"up","down"}`` branch and silently
    behaved like ``None`` — a typo got the default response.
    """
    uow = MagicMock()
    uow.tracks.get = AsyncMock(return_value=None)
    with pytest.raises(ValidationError, match="invalid energy_direction"):
        await track_suggest_next(id=1, energy_direction="sideways", uow=uow)


@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["up", "down", "flat", None])
async def test_suggest_next_accepts_documented_values(direction: str | None) -> None:
    """The four documented values (up/down/flat/None) all pass the new
    input gate. Reaching the NotFoundError below means validation cleared.
    """
    uow = MagicMock()
    uow.tracks.get = AsyncMock(return_value=None)  # downstream NotFoundError
    with pytest.raises(Exception, match="not found"):
        await track_suggest_next(id=99999, energy_direction=direction, uow=uow)
