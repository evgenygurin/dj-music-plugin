"""Set repository + set-version helpers."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.set import DjSet, DjSetItem, DjSetVersion
from app.models.track import Track
from app.repositories.base import BaseRepository
from app.shared.errors import ValidationError


class SetRepository(BaseRepository[DjSet]):
    model = DjSet

    async def version_count(self, set_id: int) -> int:
        stmt = select(func.count()).select_from(DjSetVersion).where(DjSetVersion.set_id == set_id)
        return int(await self.session.scalar(stmt) or 0)

    async def latest_version(self, set_id: int) -> DjSetVersion | None:
        stmt = (
            select(DjSetVersion)
            .where(DjSetVersion.set_id == set_id)
            .order_by(DjSetVersion.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]


class SetVersionRepository(BaseRepository[DjSetVersion]):
    model = DjSetVersion

    async def get_items(self, version_id: int) -> list[DjSetItem]:
        stmt = (
            select(DjSetItem)
            .where(DjSetItem.version_id == version_id)
            .order_by(DjSetItem.sort_index)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def create_items(self, version_id: int, track_order: list[int]) -> int:
        # Verify every track_id exists before bulk-inserting; otherwise SQLite
        # (tests, default FK enforcement off) silently writes orphans and
        # PostgreSQL raises an opaque foreign-key violation. A single batch
        # ``SELECT id IN (...)`` is cheap and produces a typed
        # ValidationError naming the bogus ids.
        if track_order:
            unique_ids = list(set(track_order))
            stmt = select(Track.id).where(Track.id.in_(unique_ids))
            existing = {row for (row,) in (await self.session.execute(stmt)).all()}
            missing = [tid for tid in unique_ids if tid not in existing]
            if missing:
                raise ValidationError(
                    f"track_order references unknown track id(s) {sorted(missing)!r}; "
                    f"verified {len(existing)}/{len(unique_ids)} exist",
                    details={"missing_track_ids": sorted(missing)},
                )
        items = [
            DjSetItem(version_id=version_id, track_id=tid, sort_index=i)
            for i, tid in enumerate(track_order)
        ]
        self.session.add_all(items)
        await self.session.flush()
        return len(items)

    async def get_latest(self, set_id: int) -> DjSetVersion | None:
        """Return the newest version for a set — MAX(id) wins."""
        stmt = (
            select(DjSetVersion)
            .where(DjSetVersion.set_id == set_id)
            .order_by(DjSetVersion.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    async def count_for_set(self, set_id: int) -> int:
        """Return the number of versions for a set."""
        stmt = select(func.count()).select_from(DjSetVersion).where(DjSetVersion.set_id == set_id)
        return int(await self.session.scalar(stmt) or 0)

    # Alias matching the older name used by some resources.
    latest_version = get_latest
