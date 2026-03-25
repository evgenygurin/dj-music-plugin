"""DJ Set repository with version management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.set import DjSet, SetItem, SetVersion
from app.repositories.base import BaseRepository


class SetRepository(BaseRepository[DjSet]):
    """Repository for :class:`DjSet` with version helpers."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DjSet)

    async def get_latest_version(self, set_id: int) -> SetVersion | None:
        """Return the most recent version for a given set, with items eager-loaded."""
        stmt = (
            select(SetVersion)
            .where(SetVersion.set_id == set_id)
            .options(selectinload(SetVersion.items))
            .order_by(SetVersion.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_version(
        self,
        set_id: int,
        items: list[dict],
        label: str | None = None,
    ) -> SetVersion:
        """Create a new version with ordered items.

        Each dict in *items* must contain at least ``track_id`` and ``sort_index``.
        """
        version = SetVersion(set_id=set_id, label=label)
        self.session.add(version)
        await self.session.flush()

        for item_data in items:
            set_item = SetItem(
                version_id=version.id,
                track_id=item_data["track_id"],
                sort_index=item_data["sort_index"],
            )
            self.session.add(set_item)
        await self.session.flush()

        return version

    async def get_version_with_items(self, version_id: int) -> SetVersion | None:
        """Load a version with items eagerly."""
        stmt = (
            select(SetVersion)
            .where(SetVersion.id == version_id)
            .options(selectinload(SetVersion.items))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
