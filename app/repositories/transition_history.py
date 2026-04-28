"""TransitionHistory repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.models.transition_history import TransitionHistory
from app.repositories.base import BaseRepository


def _best_pairs_stmt(limit: int) -> Any:
    """Build the best-pairs SELECT.

    Extracted to module level so a unit test can compile it against the
    Postgres dialect and assert ``NULLS LAST`` is present (audit O-2:
    SQLite ignores the clause silently and was hiding the prod bug —
    on Postgres ``DESC`` puts NULL first by default, swallowing the
    real "best" rows under the unscored ones).

    Audit iter 59 (T-57): pre-T-52 data left a handful of degenerate
    self-pair rows (``from_track_id == to_track_id``) on production.
    Schema validators (v1.2.51-52) prevent new ones, but the existing
    rows pollute the "best pairs" view. Filter them out at the SELECT
    so all consumers benefit.
    """
    return (
        select(TransitionHistory)
        .where(TransitionHistory.from_track_id != TransitionHistory.to_track_id)
        .order_by(TransitionHistory.overall_score.desc().nulls_last())
        .limit(limit)
    )


class TransitionHistoryRepository(BaseRepository[TransitionHistory]):
    model = TransitionHistory

    async def best_pairs(self, limit: int = 20) -> list[TransitionHistory]:
        return list((await self.session.execute(_best_pairs_stmt(limit))).scalars())

    async def reaction_counts(self) -> dict[str, int]:
        stmt = select(TransitionHistory.user_reaction, func.count()).group_by(
            TransitionHistory.user_reaction
        )
        return {r or "none": n for r, n in (await self.session.execute(stmt)).all()}
