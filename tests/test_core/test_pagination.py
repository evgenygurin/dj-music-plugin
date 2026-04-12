import pytest

from dj_music.core.utils.pagination import CursorPage, decode_cursor, encode_cursor


def test_encode_decode_roundtrip() -> None:
    assert decode_cursor(encode_cursor(42)) == 42


def test_encode_decode_zero() -> None:
    assert decode_cursor(encode_cursor(0)) == 0


def test_encode_decode_large() -> None:
    assert decode_cursor(encode_cursor(999999)) == 999999


def test_decode_invalid() -> None:
    with pytest.raises(ValueError):
        decode_cursor("not-valid")


def test_decode_empty() -> None:
    with pytest.raises(ValueError):
        decode_cursor("")


def test_cursor_page_generic() -> None:
    page: CursorPage[int] = CursorPage(items=[1, 2], next_cursor="x", total=5)
    assert len(page.items) == 2
    assert page.total == 5


def test_cursor_page_last() -> None:
    page: CursorPage[str] = CursorPage(items=["a"], next_cursor=None, total=1)
    assert page.next_cursor is None
