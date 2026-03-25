"""Tests for pagination utilities - FastMCP best practices compliance."""

import pytest

from app.core.pagination import (
    CursorPage,
    decode_cursor,
    encode_cursor,
    paginate_items,
)


# ── Cursor encoding/decoding tests ──────────────────────


def test_encode_decode_roundtrip() -> None:
    """Cursor encoding and decoding are symmetric."""
    assert decode_cursor(encode_cursor(42)) == 42


def test_encode_decode_zero() -> None:
    """Zero offset is valid."""
    assert decode_cursor(encode_cursor(0)) == 0


def test_encode_decode_large() -> None:
    """Large offsets work correctly."""
    assert decode_cursor(encode_cursor(999999)) == 999999


def test_decode_invalid() -> None:
    """Invalid cursor raises ValueError."""
    with pytest.raises(ValueError):
        decode_cursor("not-valid")


def test_decode_empty() -> None:
    """Empty cursor raises ValueError."""
    with pytest.raises(ValueError):
        decode_cursor("")


def test_cursor_page_generic() -> None:
    """CursorPage supports generic type parameters."""
    page: CursorPage[int] = CursorPage(items=[1, 2], next_cursor="x", total=5)
    assert len(page.items) == 2
    assert page.total == 5


def test_cursor_page_last() -> None:
    """Last page has None cursor."""
    page: CursorPage[str] = CursorPage(items=["a"], next_cursor=None, total=1)
    assert page.next_cursor is None


# ── FastMCP native pagination tests ─────────────────────


def test_paginate_items_first_page() -> None:
    """First page returns correct items and cursor."""
    items = list(range(100))
    page_items, next_cursor = paginate_items(items, cursor=None, page_size=10)
    
    assert len(page_items) == 10
    assert page_items == list(range(10))
    assert next_cursor is not None


def test_paginate_items_middle_page() -> None:
    """Middle page uses cursor and returns next cursor."""
    items = list(range(100))
    # Get first page to obtain cursor
    _, cursor = paginate_items(items, cursor=None, page_size=10)
    
    # Get second page
    page_items, next_cursor = paginate_items(items, cursor=cursor, page_size=10)
    
    assert len(page_items) == 10
    assert page_items == list(range(10, 20))
    assert next_cursor is not None


def test_paginate_items_last_page() -> None:
    """Last page returns None cursor."""
    items = list(range(25))
    # Get first page
    _, cursor1 = paginate_items(items, cursor=None, page_size=10)
    # Get second page
    _, cursor2 = paginate_items(items, cursor=cursor1, page_size=10)
    # Get last page (5 items)
    page_items, next_cursor = paginate_items(items, cursor=cursor2, page_size=10)
    
    assert len(page_items) == 5
    assert page_items == list(range(20, 25))
    assert next_cursor is None


def test_paginate_items_no_overlap() -> None:
    """Pages have no overlapping items."""
    items = list(range(50))
    seen = []
    cursor = None
    
    for _ in range(5):  # 5 pages of 10 items each
        page_items, cursor = paginate_items(items, cursor=cursor, page_size=10)
        # Ensure no duplicates
        for item in page_items:
            assert item not in seen
            seen.append(item)
        
        if cursor is None:
            break
    
    assert seen == items


def test_paginate_items_empty() -> None:
    """Empty sequence returns empty page."""
    items: list[int] = []
    page_items, next_cursor = paginate_items(items, cursor=None, page_size=10)
    
    assert page_items == []
    assert next_cursor is None


def test_paginate_items_single_page() -> None:
    """Sequence smaller than page_size returns all items with no cursor."""
    items = [1, 2, 3]
    page_items, next_cursor = paginate_items(items, cursor=None, page_size=10)
    
    assert page_items == items
    assert next_cursor is None


def test_paginate_items_exact_page_size() -> None:
    """Sequence exactly matching page_size returns all items with no cursor."""
    items = list(range(10))
    page_items, next_cursor = paginate_items(items, cursor=None, page_size=10)
    
    assert page_items == items
    assert next_cursor is None


def test_paginate_items_invalid_cursor() -> None:
    """Invalid cursor raises ValueError."""
    items = list(range(10))
    
    with pytest.raises(ValueError):
        paginate_items(items, cursor="invalid", page_size=10)
