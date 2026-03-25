"""Cursor-based pagination utilities aligned with FastMCP best practices.

This module provides a thin wrapper around FastMCP's native pagination utilities
while maintaining backward compatibility with existing code.
"""

import base64
from typing import Generic, Sequence, TypeVar

from fastmcp.utilities.pagination import CursorState, paginate_sequence
from pydantic import BaseModel

T = TypeVar("T")


def encode_cursor(last_id: int) -> str:
    """Encode a record ID as a base64 cursor string.
    
    Compatible with FastMCP's cursor format while using our own offset encoding.
    """
    state = CursorState(offset=last_id)
    return state.encode()


def decode_cursor(cursor: str) -> int:
    """Decode a cursor string back to a record ID. Raises ValueError if invalid.
    
    Compatible with both our legacy format and FastMCP's native format.
    """
    try:
        # Try FastMCP native format first
        state = CursorState.decode(cursor)
        return state.offset
    except ValueError:
        # Fallback to legacy format for backward compatibility
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
            if not decoded.startswith("cursor:"):
                raise ValueError(f"Invalid cursor format: {cursor}")
            return int(decoded.removeprefix("cursor:"))
        except Exception as e:
            raise ValueError(f"Invalid cursor: {cursor}") from e


def paginate_items(
    items: Sequence[T], cursor: str | None, page_size: int
) -> tuple[list[T], str | None]:
    """Paginate a sequence using FastMCP's native pagination utility.
    
    Args:
        items: Full sequence to paginate
        cursor: Optional cursor from previous request
        page_size: Maximum items per page
        
    Returns:
        Tuple of (page_items, next_cursor). next_cursor is None if no more pages.
        
    Raises:
        ValueError: If cursor is invalid
    """
    return paginate_sequence(items, cursor, page_size)


class CursorPage(BaseModel, Generic[T]):
    """Paginated result with cursor-based navigation.
    
    This maintains backward compatibility with existing code while aligning
    with FastMCP pagination patterns.
    """

    model_config = {"arbitrary_types_allowed": True}

    items: list[T]
    next_cursor: str | None
    total: int
