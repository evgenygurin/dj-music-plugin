"""``__isnull`` lookups for NULL-heavy track_features columns.

``.claude/rules/repositories.md`` documents ``key_code__isnull`` as a
canonical DSL example, and ``.claude/rules/tools.md`` warns that the
essentia/L3+ columns are largely NULL at L2 (``__gte``/``__lte`` silently
empties the result set). Yet the Filter schema (``extra="forbid"``)
declared ``__isnull`` only for ``mood`` / ``beatport_genre`` — the
documented ``key_code__isnull`` was a hard ValidationError (live probe
2026-07-03). These lookups are THE tool for "which tracks still need
analysis" queries, so pin them.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.track_features import TrackFeaturesRepository
from app.schemas.track_features import TrackFeaturesFilter

ISNULL_FIELDS = [
    "key_code__isnull",
    "bpm_confidence__isnull",
    "true_peak_db__isnull",
    "danceability__isnull",
    "dynamic_complexity__isnull",
    "spectral_complexity_mean__isnull",
    "pitch_salience_mean__isnull",
]


@pytest.mark.parametrize("field", ISNULL_FIELDS)
def test_isnull_lookup_declared_on_filter_schema(field: str) -> None:
    TrackFeaturesFilter.model_validate({field: True})  # must not raise


@pytest_asyncio.fixture
async def _tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_tables")
async def test_key_code_isnull_filters_rows(session: AsyncSession) -> None:
    keyed, unkeyed = Track(title="Keyed"), Track(title="Unkeyed")
    session.add_all([keyed, unkeyed])
    await session.flush()
    session.add_all(
        [
            TrackAudioFeaturesComputed(track_id=keyed.id, analysis_level=2, key_code=8),
            TrackAudioFeaturesComputed(track_id=unkeyed.id, analysis_level=2, key_code=None),
        ]
    )
    await session.flush()

    repo = TrackFeaturesRepository(session)
    page = await repo.filter(where={"key_code__isnull": True})
    assert [r.track_id for r in page.items] == [unkeyed.id]
    page = await repo.filter(where={"key_code__isnull": False})
    assert [r.track_id for r in page.items] == [keyed.id]
