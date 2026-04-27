"""Audit iter 47 (T-45): ``entity_aggregate`` field validation
emitted a misleading error when the caller passed an unknown field
name. Live confirmation:

    entity_aggregate(track, "distinct", field="nonexistent_field")
    -> "operation 'distinct' requires field"

The message suggested the caller forgot the parameter, when in
fact they passed it but mistyped the column name. Same drift on
sum / avg / min_max / histogram which said "requires a valid
field" — only marginally clearer.

Now both cases are distinguished:
- field omitted entirely      -> "operation X requires a ``field`` parameter"
- field provided but unknown  -> "unknown field 'X' on Track (operation 'distinct')"
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base
from app.repositories.track import TrackRepository
from app.shared.errors import ValidationError


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    repo = TrackRepository(session)
    await repo.create(title="x")
    return repo


@pytest.mark.parametrize("op", ["distinct", "sum", "avg", "min_max", "histogram"])
@pytest.mark.asyncio
async def test_unknown_field_says_unknown(op: str, repo: TrackRepository) -> None:
    """All field-required ops mention the bad field name in the error."""
    with pytest.raises(ValidationError, match=r"unknown field 'nonexistent_field'"):
        await repo.aggregate(operation=op, field="nonexistent_field")


@pytest.mark.parametrize("op", ["distinct", "sum", "avg", "min_max", "histogram"])
@pytest.mark.asyncio
async def test_omitted_field_says_requires_parameter(op: str, repo: TrackRepository) -> None:
    """When ``field`` is omitted entirely, the error names the
    parameter rather than implying the value was malformed."""
    with pytest.raises(ValidationError, match=r"requires a ``field`` parameter"):
        await repo.aggregate(operation=op, field=None)


@pytest.mark.asyncio
async def test_count_does_not_require_field(repo: TrackRepository) -> None:
    """Sanity: ``count`` works without a field — and isn't accidentally
    caught by the new validation gate."""
    n = await repo.aggregate(operation="count")
    assert n == 1
