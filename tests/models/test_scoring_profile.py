"""ScoringProfile (custom transition-scorer weight sets)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models.base import Base
from app.models.scoring_profile import ScoringProfile


@pytest.mark.asyncio
async def test_profile_weights_sum(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    p = ScoringProfile(
        name="melodic_priority",
        bpm_weight=0.15,
        harmonics_weight=0.25,
        energy_weight=0.15,
        bass_weight=0.20,
        drums_weight=0.15,
        vocals_weight=0.10,
        description="more harmony weight for melodic sets",
    )
    session.add(p)
    await session.commit()
    assert p.id is not None


@pytest.mark.asyncio
async def test_profile_weight_range(engine: AsyncEngine, session: AsyncSession) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    p = ScoringProfile(
        name="bad",
        bpm_weight=2.0,
        harmonics_weight=0.1,
        energy_weight=0.1,
        bass_weight=0.1,
        drums_weight=0.1,
        vocals_weight=0.1,
    )
    session.add(p)
    with pytest.raises(IntegrityError):
        await session.commit()
