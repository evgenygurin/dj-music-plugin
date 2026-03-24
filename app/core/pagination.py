import base64
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


def encode_cursor(last_id: int) -> str:
    """Encode a record ID as a base64 cursor string."""
    return base64.urlsafe_b64encode(f"cursor:{last_id}".encode()).decode()


def decode_cursor(cursor: str) -> int:
    """Decode a cursor string back to a record ID. Raises ValueError if invalid."""
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
        if not decoded.startswith("cursor:"):
            raise ValueError(f"Invalid cursor format: {cursor}")
        return int(decoded.removeprefix("cursor:"))
    except Exception as e:
        raise ValueError(f"Invalid cursor: {cursor}") from e


class CursorPage(BaseModel, Generic[T]):
    """Paginated result with cursor-based navigation."""

    items: list[T]
    next_cursor: str | None
    total: int
