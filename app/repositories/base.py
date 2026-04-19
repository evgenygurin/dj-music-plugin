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

from app.shared.errors import NotFoundError, ValidationError
from app.shared.filters import parse_filter
from app.shared.pagination import Page, decode_cursor, encode_cursor

M = TypeVar("M", bound=DeclarativeBase)


class BaseRepository(Generic[M]):
    """Thin async CRUD + filter. Subclass + set ``model``."""

    model: ClassVar[type[DeclarativeBase]]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── single-row ────────────────────────────────────

    async def get(self, id: int) -> M | None:
        return await self.session.get(self.model, id)  # type: ignore[arg-type]

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

        - ``where``: Django-style lookups, see ``app.shared.filters``.
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
        # Default to the first primary-key column — not "id" — so entities
        # whose PK is e.g. ``track_id`` (TrackAudioFeaturesComputed) paginate
        # without the caller having to specify ``sort``.
        if order:
            order_clauses = list(order)
        else:
            pk_cols = [c.name for c in self.model.__table__.primary_key.columns]
            order_clauses = [pk_cols[0]] if pk_cols else ["id"]
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

    # ── aggregate ─────────────────────────────────────

    async def aggregate(
        self,
        *,
        operation: str,
        field: str | None = None,
        group_by: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> Any:
        """Run a single-pass aggregate (count/sum/avg/min_max/distinct/histogram).

        Returns a scalar for ungrouped count/sum/avg, a mapping for
        ``min_max``, a list for ``distinct``/``histogram``, or — when
        ``group_by`` is set — a list of ``{group, value}`` dicts.
        """
        op = operation
        field_col = getattr(self.model, field, None) if field else None
        if op in {"sum", "avg", "min_max", "histogram"} and field_col is None:
            raise ValidationError(f"operation {op!r} requires a valid field")

        group_col = getattr(self.model, group_by, None) if group_by else None
        if group_by and group_col is None:
            raise ValidationError(f"unknown group_by field {group_by!r}")

        match op:
            case "count":
                value_expr = func.count()
            case "sum":
                value_expr = func.sum(field_col)
            case "avg":
                value_expr = func.avg(field_col)
            case "min_max":
                stmt = select(func.min(field_col), func.max(field_col)).select_from(self.model)
                for clause in parse_filter(self.model, where or {}):
                    stmt = stmt.where(clause)
                row = (await self.session.execute(stmt)).one()
                return {"min": row[0], "max": row[1]}
            case "distinct":
                if field_col is None:
                    raise ValidationError("operation 'distinct' requires field")
                stmt = select(field_col).select_from(self.model).distinct()
                for clause in parse_filter(self.model, where or {}):
                    stmt = stmt.where(clause)
                return list((await self.session.execute(stmt)).scalars().all())
            case "histogram":
                # {value: count} for discrete fields — caller buckets numeric ones.
                stmt = select(field_col, func.count()).select_from(self.model).group_by(field_col)
                for clause in parse_filter(self.model, where or {}):
                    stmt = stmt.where(clause)
                rows = (await self.session.execute(stmt)).all()
                return [{"bucket": r[0], "count": int(r[1])} for r in rows]
            case _:
                raise ValidationError(f"unsupported aggregate operation: {op!r}")

        # count / sum / avg flow
        if group_col is not None:
            stmt = select(group_col, value_expr).select_from(self.model).group_by(group_col)
            for clause in parse_filter(self.model, where or {}):
                stmt = stmt.where(clause)
            rows = (await self.session.execute(stmt)).all()
            return [{"group": r[0], "value": r[1]} for r in rows]

        stmt = select(value_expr).select_from(self.model)
        for clause in parse_filter(self.model, where or {}):
            stmt = stmt.where(clause)
        return (await self.session.execute(stmt)).scalar_one()
