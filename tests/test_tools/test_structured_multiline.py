"""Tests for multiline structured-output helper."""

from app.controllers.tools._shared.structured_multiline import split_multiline_for_json_ui


def test_split_multiline_round_trip() -> None:
    text = "a\nb\nc"
    full, lines = split_multiline_for_json_ui(text)
    assert full == text
    assert lines == ["a", "b", "c"]
    assert "\n".join(lines) == text
