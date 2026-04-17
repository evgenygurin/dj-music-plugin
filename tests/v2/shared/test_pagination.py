"""Cursor pagination tests."""

from dataclasses import dataclass

import pytest

from app.v2.shared.pagination import Page, decode_cursor, encode_cursor


@dataclass
class _FakeItem:
    id: int
    name: str


def test_encode_decode_round_trip() -> None:
    cursor = encode_cursor(42)
    assert isinstance(cursor, str)
    assert decode_cursor(cursor) == 42


def test_cursor_is_url_safe() -> None:
    cursor = encode_cursor(12345)
    assert "+" not in cursor and "/" not in cursor and "=" not in cursor


def test_decode_invalid_cursor_raises() -> None:
    with pytest.raises(ValueError):
        decode_cursor("not-a-cursor")


def test_page_construction() -> None:
    items = [_FakeItem(1, "a"), _FakeItem(2, "b")]
    page = Page(items=items, next_cursor="abc", total=None)
    assert page.items == items
    assert page.next_cursor == "abc"
    assert page.total is None


def test_page_has_more_when_cursor_present() -> None:
    page = Page(items=[_FakeItem(1, "a")], next_cursor="abc")
    assert page.has_more is True


def test_page_no_more_when_cursor_none() -> None:
    page = Page(items=[_FakeItem(1, "a")], next_cursor=None)
    assert page.has_more is False


def test_page_generic_typing() -> None:
    # Smoke check: Page[str] constructs
    page: Page[str] = Page(items=["x", "y"], next_cursor=None, total=2)
    assert page.items == ["x", "y"]
