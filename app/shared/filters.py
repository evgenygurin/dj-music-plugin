"""Django-style lookup parser for generic filtering.

Parses dict filters like ``{"bpm__gte": 120, "mood__in": ["peak_time"]}``
into SQLAlchemy clause objects. Used by ``BaseRepository.filter()``.

Supported operators:
    eq         exact match (default when no suffix)
    ne         not equal
    lt / lte   less than / less-or-equal
    gt / gte   greater than / greater-or-equal
    in         value IN list
    not_in     value NOT IN list
    icontains  case-insensitive substring
    contains   case-sensitive substring
    startswith case-sensitive prefix
    endswith   case-sensitive suffix
    isnull     IS NULL if True, IS NOT NULL if False
    range      BETWEEN [lo, hi] — value must be a 2-tuple/list
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Any

from sqlalchemy import Column
from sqlalchemy.sql.elements import ColumnElement

from app.shared.errors import ValidationError

# ── Operator table ────────────────────────────────────


def _eq(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col == val  # type: ignore[no-any-return]


def _ne(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col != val  # type: ignore[no-any-return]


def _lt(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col < val  # type: ignore[no-any-return]


def _lte(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col <= val  # type: ignore[no-any-return]


def _gt(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col > val  # type: ignore[no-any-return]


def _gte(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col >= val  # type: ignore[no-any-return]


def _in(col: Column[Any], val: Any) -> ColumnElement[bool]:
    if not isinstance(val, list | tuple | set):
        raise ValidationError(f"'in' operator requires list/tuple, got {type(val).__name__}")
    return col.in_(list(val))


def _not_in(col: Column[Any], val: Any) -> ColumnElement[bool]:
    if not isinstance(val, list | tuple | set):
        raise ValidationError(f"'not_in' operator requires list/tuple, got {type(val).__name__}")
    return ~col.in_(list(val))


_LIKE_ESCAPE_CHAR = "\\"


def _escape_like(val: Any) -> str:
    """Escape LIKE/ILIKE wildcards (``%``, ``_``) in a user-supplied value.

    Without this, a filter value containing ``%`` or ``_`` is interpreted
    as a SQL wildcard instead of a literal character — not an injection
    (the value is still a bound parameter), but it silently changes match
    semantics (e.g. ``icontains="100%"`` matching any string starting with
    "100" instead of the literal substring "100%").
    """
    text = str(val)
    text = text.replace(_LIKE_ESCAPE_CHAR, _LIKE_ESCAPE_CHAR * 2)
    text = text.replace("%", f"{_LIKE_ESCAPE_CHAR}%")
    text = text.replace("_", f"{_LIKE_ESCAPE_CHAR}_")
    return text


def _icontains(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col.ilike(f"%{_escape_like(val)}%", escape=_LIKE_ESCAPE_CHAR)


def _contains(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col.like(f"%{_escape_like(val)}%", escape=_LIKE_ESCAPE_CHAR)


def _startswith(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col.like(f"{_escape_like(val)}%", escape=_LIKE_ESCAPE_CHAR)


def _endswith(col: Column[Any], val: Any) -> ColumnElement[bool]:
    return col.like(f"%{_escape_like(val)}", escape=_LIKE_ESCAPE_CHAR)


def _isnull(col: Column[Any], val: Any) -> ColumnElement[bool]:
    if not isinstance(val, bool):
        raise ValidationError(f"'isnull' operator requires bool, got {type(val).__name__}")
    return col.is_(None) if val else col.is_not(None)


def _range(col: Column[Any], val: Any) -> ColumnElement[bool]:
    if not (isinstance(val, list | tuple) and len(val) == 2):
        raise ValidationError(f"'range' operator requires [lo, hi], got {val!r}")
    return col.between(val[0], val[1])


LOOKUP_OPERATORS: dict[str, Callable[[Column[Any], Any], ColumnElement[bool]]] = {
    "eq": _eq,
    "ne": _ne,
    "lt": _lt,
    "lte": _lte,
    "gt": _gt,
    "gte": _gte,
    "in": _in,
    "not_in": _not_in,
    "icontains": _icontains,
    "contains": _contains,
    "startswith": _startswith,
    "endswith": _endswith,
    "isnull": _isnull,
    "range": _range,
}


def split_lookup(key: str) -> tuple[str, str]:
    """Split ``"bpm__gte"`` into ``("bpm", "gte")``. Plain ``"bpm"`` → ``("bpm", "eq")``.

    Uses ``rsplit`` so field names with underscores (``track_id__in``) work correctly.
    """
    if "__" not in key:
        return key, "eq"
    field, op = key.rsplit("__", 1)
    if op not in LOOKUP_OPERATORS:
        # Underscore in field name, no real operator — treat whole thing as field.
        return key, "eq"
    return field, op


def parse_filter(
    model: type[Any],
    where: Mapping[str, Any],
    *,
    allowed_fields: Collection[str] | None = None,
) -> list[ColumnElement[bool]]:
    """Parse a ``where`` dict into a list of SQLAlchemy clauses.

    Args:
        model: SQLAlchemy declarative class.
        where: ``{field[__op]: value}`` mapping.
        allowed_fields: optional whitelist — fields not in the set raise
            ``ValidationError``. ``None`` means all model columns are allowed.

    Raises:
        ValidationError: on unknown field, unknown operator, or disallowed field.
    """
    clauses: list[ColumnElement[bool]] = []
    for raw_key, value in where.items():
        field, op = split_lookup(raw_key)
        if allowed_fields is not None and field not in allowed_fields:
            raise ValidationError(
                f"field {field!r} not allowed (allowed: {sorted(allowed_fields)})",
                details={"field": field, "allowed": list(allowed_fields)},
            )
        column = getattr(model, field, None)
        if column is None:
            raise ValidationError(
                f"unknown field {field!r} on model {model.__name__}",
                details={"field": field, "model": model.__name__},
            )
        if op not in LOOKUP_OPERATORS:
            raise ValidationError(
                f"unknown operator {op!r} (supported: {sorted(LOOKUP_OPERATORS)})",
                details={"operator": op, "supported": sorted(LOOKUP_OPERATORS)},
            )
        clauses.append(LOOKUP_OPERATORS[op](column, value))
    return clauses


def parse_django_filters(
    model: type[Any],
    where: Mapping[str, Any],
    *,
    allowed_fields: Collection[str] | None = None,
) -> list[ColumnElement[bool]]:
    """Alias of :func:`parse_filter` — name used by entity_* tools (Phase 3)."""
    return parse_filter(model, where, allowed_fields=allowed_fields)


def normalize_bare_fields(where: Mapping[str, Any]) -> dict[str, Any]:
    """Map bare field names to implicit ``__eq`` lookups.

    Django-style shorthand ``{"id": 1}`` becomes ``{"id__eq": 1}`` so it
    passes Pydantic filter-schema validation (which declares explicit
    ``__eq``/``__in``/... suffixes). Keys already carrying any valid
    ``__<op>`` suffix are passed through untouched. Preserves the
    shorthand that ``parse_filter`` already accepted via
    :func:`split_lookup` — prevents a regression for clients that were
    relying on bare equality before entity_list/aggregate switched to
    Pydantic-schema validation.
    """
    out: dict[str, Any] = {}
    for key, value in where.items():
        if "__" not in key:
            out[f"{key}__eq"] = value
            continue
        # Preserve bare fields whose name happens to contain "__" but whose
        # suffix isn't a real operator (rare, but possible for obscure
        # column names). split_lookup treats those as bare already.
        _, op = split_lookup(key)
        if op == "eq" and not key.endswith("__eq"):
            out[f"{key}__eq"] = value
        else:
            out[key] = value
    return out
