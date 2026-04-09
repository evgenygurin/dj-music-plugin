"""DJ Set repository with version management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.set import DjSet, SetItem, SetVersion
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from app.core.utils.pagination import CursorPage
    from app.db.models.set import SetConstraint, SetFeedback


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
        items: list[dict[str, Any]] | list[int],
        label: str | None = None,
        gen_meta: str | None = None,
    ) -> SetVersion:
        """Create a new version with ordered items.

        *items* can be:
        - list[int]: track IDs (sort_index assigned automatically)
        - list[dict]: dicts with ``track_id``, ``sort_index``, optional ``pinned``

        *gen_meta*: optional JSON string with generator run metadata.
        """
        version = SetVersion(set_id=set_id, label=label, generator_run_meta=gen_meta)
        self.session.add(version)
        await self.session.flush()

        if items and isinstance(items[0], int):
            for idx, tid in enumerate(items):
                self.session.add(SetItem(version_id=version.id, track_id=tid, sort_index=idx))
        else:
            for item_data in items:
                self.session.add(
                    SetItem(
                        version_id=version.id,
                        track_id=item_data["track_id"],  # type: ignore[index]
                        sort_index=item_data["sort_index"],  # type: ignore[index]
                        pinned=item_data.get("pinned", False),  # type: ignore[union-attr]
                    )
                )
        await self.session.flush()

        return version

    async def get_version_items(self, version_id: int) -> list[SetItem]:
        """Return ordered set items for a specific version.

        Commonly used by tools to iterate over tracks in a set version
        for scoring, delivery, and quality review.
        """
        stmt = select(SetItem).where(SetItem.version_id == version_id).order_by(SetItem.sort_index)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_version_with_items(self, version_id: int) -> SetVersion | None:
        """Load a version with items eagerly."""
        stmt = (
            select(SetVersion)
            .where(SetVersion.id == version_id)
            .options(selectinload(SetVersion.items))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def load_version_with_items(
        self,
        set_id: int,
        version_label: str | None = None,
    ) -> tuple[SetVersion, list[SetItem]] | None:
        """Load a set version and its ordered items in one call.

        If *version_label* is given, look up that specific version;
        otherwise return the latest version.  Returns ``None`` when no
        matching version exists.
        """
        if version_label:
            version = await self.get_version_by_label(set_id, version_label)
        else:
            version = await self.get_latest_version(set_id)
        if version is None:
            return None
        items = await self.get_version_items(version.id)
        return version, items

    async def search_by_name(self, query: str) -> DjSet | None:
        """Find set by case-insensitive name search."""
        stmt = select(DjSet).where(DjSet.name.ilike(f"%{query}%")).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_name_list(self, query: str, limit: int = 10) -> list[DjSet]:
        """Search sets by name, return list."""
        stmt = select(DjSet).where(DjSet.name.ilike(f"%{query}%")).order_by(DjSet.id).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_filtered(
        self,
        *,
        template: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[DjSet]:
        """List sets with optional template filter."""

        stmt = select(DjSet)
        if template is not None:
            stmt = stmt.where(DjSet.template_name == template)
        return await self._paginate(stmt, limit=limit, cursor=cursor)

    async def get_latest_versions(self, set_id: int, count: int = 2) -> list[SetVersion]:
        """Return N most recent versions for a set."""
        stmt = (
            select(SetVersion)
            .where(SetVersion.set_id == set_id)
            .order_by(SetVersion.id.desc())
            .limit(count)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_version_by_label(
        self,
        set_id: int,
        label: str,
    ) -> SetVersion | None:
        """Find a version by its label."""
        stmt = select(SetVersion).where(
            SetVersion.set_id == set_id,
            SetVersion.label == label,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_version_with_meta(
        self,
        set_id: int,
        track_order: list[int],
        label: str = "v1",
        gen_meta: str | None = None,
    ) -> SetVersion:
        """Backward-compat alias — use create_version() instead."""
        return await self.create_version(set_id, track_order, label=label, gen_meta=gen_meta)

    async def create_version_with_items(
        self,
        set_id: int,
        items: list[dict[str, Any]],
        label: str | None = None,
    ) -> SetVersion:
        """Backward-compat alias — use create_version() instead."""
        return await self.create_version(set_id, items, label=label)

    async def add_constraint(self, constraint: SetConstraint) -> SetConstraint:
        """Persist a set constraint."""
        self.session.add(constraint)
        await self.session.flush()
        return constraint

    async def remove_constraint(self, constraint_id: int) -> bool:
        """Remove a constraint by ID."""
        from app.db.models.set import SetConstraint

        stmt = select(SetConstraint).where(SetConstraint.id == constraint_id)
        result = await self.session.execute(stmt)
        constraint = result.scalar_one_or_none()
        if constraint is None:
            return False
        await self.session.delete(constraint)
        await self.session.flush()
        return True

    async def add_feedback(self, feedback: SetFeedback) -> SetFeedback:
        """Persist set feedback."""
        self.session.add(feedback)
        await self.session.flush()
        return feedback
