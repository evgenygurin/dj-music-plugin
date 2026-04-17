"""Generic async BaseRepository[M].

Per blueprint §10. Provides 9 methods covering the common CRUD + filter
surface. Entity-specific repositories subclass and add domain methods.

Repositories **flush but never commit** — transaction boundary is the tool
call, managed by DbSessionMiddleware in Phase 5.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.v2.shared.errors import NotFoundError, ValidationError
from app.v2.shared.filters import parse_filter
from app.v2.shared.pagination import Page, decode_cursor, encode_cursor

M = TypeVar("M", bound=DeclarativeBase)


class BaseRepository(Generic[M]):
    """Thin async CRUD + filter. Subclass + set ``model``."""

    model: ClassVar[type[DeclarativeBase]]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── single-row ────────────────────────────────────

    async def get(self, id: int) -> M | None:
        return await self.session.get(self.model, id)

    async def exists(self, id: int) -> bool:
        return (await self.get(id)) is not None

    async def create(self, **data: Any) -> M:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj  # type: ignore[return-value]

    async def update(self, id: int, **data: Any) -> M:
        obj = await self.get(id)
        if obj is None:
            raise NotFoundError(self.model.__name__, id)
        for key, value in data.items():
            if not hasattr(obj, key):
                raise ValidationError(f"unknown field {key!r} on {self.model.__name__}")
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> None:
        obj = await self.get(id)
        if obj is None:
            raise NotFoundError(self.model.__name__, id)
        await self.session.delete(obj)
        await self.session.flush()

    # ── collection ────────────────────────────────────

    async def count(self, *, where: dict[str, Any] | None = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        for clause in parse_filter(self.model, where or {}):
            stmt = stmt.where(clause)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def filter(
        self,
        *,
        where: dict[str, Any] | None = None,
        order: Sequence[str] | None = None,
        limit: int = 50,
        cursor: str | None = None,
        with_total: bool = False,
    ) -> Page[M]:
        """Filter + sort + paginate.

        - ``where``: Django-style lookups, see ``app.v2.shared.filters``.
        - ``order``: list of ``field`` or ``field_asc`` / ``field_desc``.
        - ``limit``: page size. Fetches limit+1 to detect hasMore.
        - ``cursor``: opaque cursor from prior page's ``next_cursor``.
        - ``with_total``: if True, runs a separate ``count()`` (extra query).
        """
        stmt = select(self.model)

        # WHERE
        for clause in parse_filter(self.model, where or {}):
            stmt = stmt.where(clause)

        # Keyset pagination: the outermost sort col is used for cursor.
        order_clauses = list(order or ["id"])
        # If cursor present, apply keyset predicate on the first sort field.
        if cursor is not None:
            cursor_id = decode_cursor(cursor)
            first_field = order_clauses[0].removesuffix("_desc").removesuffix("_asc")
            column = getattr(self.model, first_field, None)
            if column is None:
                raise ValidationError(f"unknown order field {first_field!r}")
            if order_clauses[0].endswith("_desc"):
                stmt = stmt.where(column < cursor_id)
            else:
                stmt = stmt.where(column > cursor_id)

        # ORDER BY
        for spec in order_clauses:
            if spec.endswith("_desc"):
                field = spec.removesuffix("_desc")
                direction = "desc"
            elif spec.endswith("_asc"):
                field = spec.removesuffix("_asc")
                direction = "asc"
            else:
                field = spec
                direction = "asc"
            column = getattr(self.model, field, None)
            if column is None:
                raise ValidationError(f"unknown order field {field!r}")
            stmt = stmt.order_by(column.desc() if direction == "desc" else column.asc())

        stmt = stmt.limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        items = rows[:limit]

        next_cursor: str | None = None
        if has_more and items:
            first_field = order_clauses[0].removesuffix("_desc").removesuffix("_asc")
            last_row = items[-1]
            next_cursor = encode_cursor(int(getattr(last_row, first_field)))

        total: int | None = None
        if with_total:
            total = await self.count(where=where)

        return Page(items=items, next_cursor=next_cursor, total=total)  # type: ignore[arg-type]
