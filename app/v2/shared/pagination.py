"""Cursor-based pagination primitives.

Cursors encode an integer row ID as a URL-safe base64 string. This keeps
cursors opaque to clients (no raw row IDs leak) and URL-embeddable.

Repository ``filter()`` / ``list()`` methods return ``Page[M]``; callers
propagate ``page.next_cursor`` to fetch subsequent pages.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Generic, TypeVar

M = TypeVar("M")


def encode_cursor(row_id: int) -> str:
    """Encode a row ID as a URL-safe opaque cursor."""
    raw = str(row_id).encode("ascii")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(cursor: str) -> int:
    """Decode a cursor back to its row ID.

    Raises ``ValueError`` on malformed input.
    """
    try:
        # base64 needs padding; add enough to be safe.
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
        return int(raw)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid cursor: {cursor!r}") from exc


@dataclass(slots=True)
class Page(Generic[M]):
    """A page of results with an optional cursor for the next page.

    ``total`` is optional (counting is expensive; only set when requested).
    ``next_cursor`` is ``None`` when no more pages remain.
    """

    items: list[M]
    next_cursor: str | None = None
    total: int | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None
