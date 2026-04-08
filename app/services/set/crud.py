"""Set CRUD sub-service — create, read, update, delete, constraints, feedback."""

from __future__ import annotations

import json as _json
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.core.utils.pagination import CursorPage
from app.db.models.set import DjSet, SetConstraint, SetFeedback, SetItem, SetVersion
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository


class SetCrudService:
    """CRUD, versioning reads, constraints, and feedback for DJ sets."""

    def __init__(
        self,
        set_repo: SetRepository,
        track_repo: TrackRepository,
    ) -> None:
        self._sets = set_repo
        self._tracks = track_repo

    # ── Read ─────────────────────────────────────────

    async def get_by_id(self, set_id: int) -> DjSet:
        dj_set = await self._sets.get_by_id(set_id)
        if dj_set is None:
            raise NotFoundError("Set", set_id)
        return dj_set

    async def get_by_query(self, query: str) -> DjSet:
        """Find set by name search."""
        dj_set = await self._sets.search_by_name(query)
        if dj_set is None:
            raise NotFoundError("Set", query)
        return dj_set

    async def list_all(
        self,
        *,
        template: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[DjSet]:
        return await self._sets.list_filtered(template=template, limit=limit, cursor=cursor)

    async def get_latest_version(self, set_id: int) -> SetVersion | None:
        return await self._sets.get_latest_version(set_id)

    async def get_version_items(self, version_id: int) -> list[SetItem]:
        return await self._sets.get_version_items(version_id)

    async def get_version_by_label(self, set_id: int, label: str) -> SetVersion | None:
        return await self._sets.get_version_by_label(set_id, label)

    async def get_two_latest_versions(self, set_id: int) -> list[SetVersion]:
        return await self._sets.get_latest_versions(set_id, count=2)

    async def get_version_by_id(self, version_id: int) -> SetVersion | None:
        return await self._sets.get_version_with_items(version_id)

    async def get_version_track_ids(self, version_id: int) -> list[int]:
        items = await self._sets.get_version_items(version_id)
        return [item.track_id for item in items]

    # ── Write ────────────────────────────────────────

    async def create(
        self,
        name: str,
        description: str | None = None,
        target_duration_ms: int | None = None,
        template: str | None = None,
    ) -> DjSet:
        if not name:
            raise ValidationError("name is required")
        dj_set = DjSet(
            name=name,
            description=description,
            target_duration_ms=target_duration_ms,
            template_name=template,
        )
        return await self._sets.create(dj_set)

    async def update(self, set_id: int, **fields: Any) -> DjSet:
        dj_set = await self.get_by_id(set_id)
        for key, value in fields.items():
            if hasattr(dj_set, key):
                setattr(dj_set, key, value)
        return await self._sets.update(dj_set)

    async def delete(self, set_id: int) -> bool:
        return await self._sets.delete(set_id)

    async def add_constraint(
        self,
        set_id: int,
        constraint_type: str,
        constraint_value: Any,
    ) -> SetConstraint:
        await self.get_by_id(set_id)  # verify exists
        value = (
            _json.dumps(constraint_value)
            if isinstance(constraint_value, dict | list)
            else constraint_value
        )
        constraint = SetConstraint(
            set_id=set_id,
            constraint_type=constraint_type,
            constraint_value=value,
        )
        return await self._sets.add_constraint(constraint)

    async def remove_constraint(self, constraint_id: int) -> bool:
        return await self._sets.remove_constraint(constraint_id)

    async def add_feedback(
        self,
        version_id: int,
        rating: int,
        feedback_type: str = "general",
        notes: str | None = None,
        set_item_id: int | None = None,
    ) -> SetFeedback:
        feedback = SetFeedback(
            version_id=version_id,
            rating=rating,
            feedback_type=feedback_type,
            notes=notes,
            set_item_id=set_item_id,
        )
        return await self._sets.add_feedback(feedback)
