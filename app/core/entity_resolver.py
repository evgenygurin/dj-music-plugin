from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class EntityRef:
    """Parsed entity reference."""

    type: Literal["id", "ym_id", "query"]
    value: Any  # int for id, str for ym_id/query


def parse_entity_ref(ref: int | str) -> EntityRef:
    """Parse flexible entity reference.

    Supports: numeric ID (42 or "42"), prefixed ("ym:12345"), text query ("Aphex Twin").
    Raises ValueError if empty.
    """
    if isinstance(ref, int):
        return EntityRef(type="id", value=ref)

    ref_str = str(ref).strip()
    if not ref_str:
        raise ValueError("Entity reference cannot be empty")

    # Try numeric
    try:
        return EntityRef(type="id", value=int(ref_str))
    except ValueError:
        pass

    # Try ym: prefix
    if ref_str.startswith("ym:"):
        return EntityRef(type="ym_id", value=ref_str[3:])

    # Default: text query
    return EntityRef(type="query", value=ref_str)
