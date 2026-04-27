"""Generic async BaseRepository[M].

Per blueprint §10. Provides 9 methods covering the common CRUD + filter
surface. Entity-specific repositories subclass and add domain methods.

Repositories **flush but never commit** — transaction boundary is the tool
call, managed by DbSessionMiddleware in Phase 5.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, ClassVar, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.shared.errors import NotFoundError, ValidationError
from app.shared.filters import parse_filter
from app.shared.pagination import Page, decode_cursor, encode_cursor

M = TypeVar("M", bound=DeclarativeBase)


# Audit iter 50 (T-48): asyncpg ``ForeignKeyViolationError`` and
# friends leaked raw SQL trace ("insert or update on table … violates
# foreign key constraint", with the full SQL + parameters dump) to
# MCP clients. Convert to a typed ``ValidationError`` so callers see
# a clean, actionable message — and the SQL stays out of logs.
_FK_DETAIL_RE = re.compile(
    r"Key \(([^)]+)\)=\(([^)]+)\) is not present in table \"([^\"]+)\"",
)


def _integrity_error_to_validation(exc: IntegrityError, model_name: str) -> ValidationError:
    """Map an asyncpg ``IntegrityError`` to a typed ``ValidationError``.

    Recognises FK violations and unique-key collisions; falls back to
    a generic "integrity violation" message when the detail string
    doesn't match the known patterns.
    """
    body = str(exc.orig) if exc.orig is not None else str(exc)
    fk_match = _FK_DETAIL_RE.search(body)
    if fk_match:
        col, value, parent_table = fk_match.groups()
        return ValidationError(
            f"foreign key violation on {model_name}.{col}: "
            f"value {value!r} does not exist in {parent_table}",
            details={"column": col, "value": value, "parent_table": parent_table},
        )
    if "duplicate key" in body.lower() or "unique constraint" in body.lower():
        return ValidationError(
            f"unique constraint violation on {model_name}",
            details={"orig": body[:200]},
        )
    return ValidationError(
        f"integrity violation on {model_name}",
        details={"orig": body[:200]},
    )


def _is_integer_column(column: Any) -> bool:
    """True iff the column's Python type can round-trip through ``int()``.

    Used by ``BaseRepository.filter`` to gate cursor pagination - the
    cursor is encoded as a single integer, so non-integer sort fields
    can't be safely paginated by cursor without a composite encoding
    (out of scope for the audit fix; raise typed error instead).
    """
    try:
        py_type = column.type.python_type
    except (AttributeError, NotImplementedError):
        return False
    return py_type is int or (isinstance(py_type, type) and issubclass(py_type, int))


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
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc, self.model.__name__) from exc
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
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc, self.model.__name__) from exc
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> None:
        obj = await self.get(id)
        if obj is None:
            raise NotFoundError(self.model.__name__, id)
        await self.session.delete(obj)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc, self.model.__name__) from exc

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
            pk_cols = [c.name for c in self.model.__table__.primary_key.columns]  # type: ignore[attr-defined]
            order_clauses = [pk_cols[0]] if pk_cols else ["id"]
        # If cursor present, apply keyset predicate on the first sort field.
        # Cursor pagination only supports integer-comparable sort fields
        # (the cursor is encoded as ``int``). Non-integer sort fields like
        # ``created_at`` (datetime) or ``mood_confidence`` (nullable float)
        # crashed with ``int() argument must be a string, ...`` when the
        # encoder tried to coerce the column value (audit iter 35).
        # Detect up front and raise a typed error instead.
        if cursor is not None:
            first_field = order_clauses[0].removesuffix("_desc").removesuffix("_asc")
            column = getattr(self.model, first_field, None)
            if column is None:
                raise ValidationError(f"unknown order field {first_field!r}")
            if not _is_integer_column(column):
                raise ValidationError(
                    f"cursor pagination requires an integer sort field; "
                    f"{first_field!r} is not integer-comparable. "
                    f"Sort by an int column (e.g. ``id``) when paginating "
                    f"with ``cursor``.",
                    details={"first_field": first_field},
                )
            cursor_id = decode_cursor(cursor)
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
            column = getattr(self.model, first_field, None)
            # Audit iter 35: only emit a cursor when the first sort field
            # is integer-comparable. ``next_cursor=None`` on non-integer
            # sorts signals end-of-stream cleanly instead of crashing
            # ``int(datetime)`` / ``int(None)`` in the encoder.
            if column is not None and _is_integer_column(column):
                last_row = items[-1]
                value = getattr(last_row, first_field)
                if value is not None:
                    next_cursor = encode_cursor(int(value))

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
        # Audit iter 47 (T-45): distinguish "field not provided" from
        # "field provided but unknown on the model". The prior message
        # ``operation 'X' requires a valid field`` was emitted for both
        # cases — callers that mistyped a column name got an error
        # suggesting they forgot the parameter entirely.
        if op in {"sum", "avg", "min_max", "histogram", "distinct"}:
            if field is None:
                raise ValidationError(f"operation {op!r} requires a ``field`` parameter")
            if field_col is None:
                raise ValidationError(
                    f"unknown field {field!r} on {self.model.__name__} (operation {op!r})"
                )

        # Audit iter 4: ``sum`` / ``avg`` on a non-numeric column leaked
        # the raw asyncpg ``function avg(character varying) does not
        # exist`` to MCP clients. Validate the column's Python type up
        # front and raise a typed ValidationError instead of letting
        # SQL fail.
        if op in {"sum", "avg"} and field_col is not None:
            try:
                py_type = field_col.type.python_type
            except (AttributeError, NotImplementedError):
                py_type = None
            numeric_types = (int, float)
            try:
                from decimal import Decimal

                numeric_types = (int, float, Decimal)  # type: ignore[assignment]
            except ImportError:
                pass
            if py_type is None or not issubclass(py_type, numeric_types):
                raise ValidationError(
                    f"operation {op!r} requires a numeric field; "
                    f"{field!r} has type {py_type.__name__ if py_type else 'unknown'}"
                )

        group_col = getattr(self.model, group_by, None) if group_by else None
        if group_by and group_col is None:
            raise ValidationError(f"unknown group_by field {group_by!r}")

        value_expr: Any
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
                # Field validity already checked up front (audit iter 47).
                assert field_col is not None  # type narrowing for mypy
                stmt = select(field_col).select_from(self.model).distinct()
                for clause in parse_filter(self.model, where or {}):
                    stmt = stmt.where(clause)
                return list((await self.session.execute(stmt)).scalars().all())
            case "histogram":
                # {value: count} for discrete fields — caller buckets numeric ones.
                stmt = select(field_col, func.count()).select_from(self.model).group_by(field_col)  # type: ignore[arg-type]
                for clause in parse_filter(self.model, where or {}):
                    stmt = stmt.where(clause)
                rows = (await self.session.execute(stmt)).all()
                return [{"bucket": r[0], "count": int(r[1])} for r in rows]
            case _:
                raise ValidationError(f"unsupported aggregate operation: {op!r}")

        # count / sum / avg flow.
        #
        # Audit iter 18 (T-18): Postgres ``AVG(integer_column)`` returns
        # ``NUMERIC``, which asyncpg surfaces as ``Decimal``. Pydantic
        # serialises ``Decimal`` as a JSON string ("9.16..."), so callers
        # got a string where they expected a number. Coerce to ``float``
        # for ``avg`` (always continuous) and to native ``int`` / ``float``
        # for ``sum`` (matches the column type). ``count`` stays an int.
        def _coerce_numeric(value: Any) -> Any:
            from decimal import Decimal

            if value is None:
                return None
            if isinstance(value, Decimal):
                return (
                    float(value)
                    if op in {"avg"}
                    else int(value)
                    if op == "count"
                    else float(value)
                )
            return value

        if group_col is not None:
            stmt = select(group_col, value_expr).select_from(self.model).group_by(group_col)
            for clause in parse_filter(self.model, where or {}):
                stmt = stmt.where(clause)
            rows = (await self.session.execute(stmt)).all()
            return [{"group": r[0], "value": _coerce_numeric(r[1])} for r in rows]

        stmt = select(value_expr).select_from(self.model)
        for clause in parse_filter(self.model, where or {}):
            stmt = stmt.where(clause)
        raw = (await self.session.execute(stmt)).scalar_one()
        # ``sum`` / ``avg`` over zero rows (or all-NULL) returns None from
        # Postgres. AggregateResult.value is non-nullable, so coalesce to 0
        # for numeric ops and keep ``count`` at its real value.
        if raw is None and op in {"sum", "avg"}:
            return 0
        return _coerce_numeric(raw)
