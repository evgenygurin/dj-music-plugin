"""Resource metadata constants + registration tests."""

from __future__ import annotations

from app.v2.resources._shared import (
    ANNOTATIONS_READ_ONLY,
    RESOURCE_META,
    json_dump,
)


def test_annotations_read_only_is_dict() -> None:
    assert isinstance(ANNOTATIONS_READ_ONLY, dict)
    assert ANNOTATIONS_READ_ONLY["readOnlyHint"] is True
    assert ANNOTATIONS_READ_ONLY["idempotentHint"] is True


def test_resource_meta_has_version() -> None:
    assert "version" in RESOURCE_META
    assert isinstance(RESOURCE_META["version"], str)


def test_json_dump_returns_string() -> None:
    out = json_dump({"a": 1, "b": [2, 3]})
    assert isinstance(out, str)
    assert '"a":1' in out.replace(" ", "")


def test_json_dump_handles_nested() -> None:
    out = json_dump({"nested": {"list": [1, 2, {"k": "v"}]}})
    assert "nested" in out and "list" in out and "v" in out


def test_json_dump_preserves_unicode() -> None:
    out = json_dump({"name": "Детройт"})
    assert "Детройт" in out
