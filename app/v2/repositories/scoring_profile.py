"""ScoringProfile repository."""

from __future__ import annotations

from sqlalchemy import select

from app.v2.models.scoring_profile import ScoringProfile
from app.v2.repositories.base import BaseRepository


class ScoringProfileRepository(BaseRepository[ScoringProfile]):
    model = ScoringProfile

    async def get_by_name(self, name: str) -> ScoringProfile | None:
        stmt = select(ScoringProfile).where(ScoringProfile.name == name).limit(1)
        return await self.session.scalar(stmt)
