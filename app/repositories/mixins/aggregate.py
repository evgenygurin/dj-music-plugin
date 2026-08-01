# mypy: disable-error-code="attr-defined"
"""AggregateMixin — separates aggregate query logic from BaseRepository (SRP).

BaseRepository was a God class handling CRUD, filter, pagination, AND
aggregation. This mixin extracts the ``aggregate()`` method,
leaving the base class focused on CRUD + filter.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.shared.errors import ValidationError
from app.shared.filters import parse_filter


class AggregateMixin:
    """Mixin providing the ``aggregate()`` method.

    Requires ``self.model`` (SQLAlchemy model class) and ``self._execute()``
    (statement executor). Satisfied by any BaseRepository subclass.
    """

    async def aggregate(
        self,
        *,
        operation: str,
        field: str | None = None,
        group_by: str | None = None,
        where: dict[str, Any] | None = None,
        bin_size: float | None = None,
    ) -> Any:
        """Run a single-pass aggregate (count/sum/avg/min_max/distinct/histogram)."""
        op = operation
        field_col = getattr(self.model, field, None) if field else None

        if op in {"sum", "avg", "min_max", "histogram", "distinct"}:
            if field is None:
                raise ValidationError(f"operation {op!r} requires a ``field`` parameter")
            if field_col is None:
                raise ValidationError(
                    f"unknown field {field!r} on {self.model.__name__} (operation {op!r})"
                )

        if op in {"sum", "avg", "min_max"} and field_col is not None:
            try:
                py_type = field_col.type.python_type
            except (AttributeError, NotImplementedError):
                py_type = None
            if py_type is bool:
                raise ValidationError(
                    f"operation {op!r} is not defined for boolean field {field!r}; "
                    "use operation 'distinct' or a filtered 'count' instead"
                )
            numeric_types = (int, float)
            try:
                from decimal import Decimal

                numeric_types = (int, float, Decimal)  # type: ignore[assignment]
            except ImportError:
                pass
            if op in {"sum", "avg"} and (
                py_type is None or not issubclass(py_type, numeric_types)
            ):
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
                row = (await self._execute(stmt)).one()
                return {"min": row[0], "max": row[1]}
            case "distinct":
                assert field_col is not None
                stmt = select(field_col).select_from(self.model).distinct()
                for clause in parse_filter(self.model, where or {}):
                    stmt = stmt.where(clause)
                return list((await self._execute(stmt)).scalars().all())
            case "histogram":
                assert field_col is not None
                try:
                    py_type = field_col.type.python_type
                except (AttributeError, NotImplementedError):
                    py_type = None
                is_continuous = py_type is float
                effective_bin = bin_size
                if is_continuous and effective_bin is None:
                    span_stmt = select(func.min(field_col), func.max(field_col)).select_from(
                        self.model
                    )
                    for clause in parse_filter(self.model, where or {}):
                        span_stmt = span_stmt.where(clause)
                    span_row = (await self._execute(span_stmt)).one()
                    lo, hi = span_row[0], span_row[1]
                    if lo is not None and hi is not None and hi > lo:
                        effective_bin = (float(hi) - float(lo)) / 30.0
                    else:
                        effective_bin = 1.0
                if effective_bin is not None and effective_bin > 0:
                    bucket_expr = func.floor(field_col / effective_bin) * effective_bin
                else:
                    bucket_expr = field_col
                stmt = (
                    select(bucket_expr.label("bucket"), func.count())
                    .select_from(self.model)
                    .group_by(bucket_expr)
                    .order_by(bucket_expr)
                )
                for clause in parse_filter(self.model, where or {}):
                    stmt = stmt.where(clause)
                rows = (await self._execute(stmt)).all()
                return [{"bucket": r[0], "count": int(r[1])} for r in rows]
            case _:
                raise ValidationError(f"unsupported aggregate operation: {op!r}")

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
            rows = (await self._execute(stmt)).all()
            return [{"group": r[0], "value": _coerce_numeric(r[1])} for r in rows]

        stmt = select(value_expr).select_from(self.model)
        for clause in parse_filter(self.model, where or {}):
            stmt = stmt.where(clause)
        raw = (await self._execute(stmt)).scalar_one()
        if raw is None and op in {"sum", "avg"}:
            return 0
        return _coerce_numeric(raw)
