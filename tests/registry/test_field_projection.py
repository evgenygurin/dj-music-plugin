"""Regression tests for ``resolve_field_projection``.

The ``fields`` parameter on ``entity_list`` / ``entity_get`` was declared
in tool signatures since v1.0 but never applied to the response — every
call returned the full row regardless of what the caller asked for.
This module pins the projection logic and the four input shapes the
helper must accept (preset name / native list / JSON-string / CSV).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.registry.entity import resolve_field_projection


def _config(presets: dict[str, Any], default: str = "id") -> Any:
    cfg = MagicMock()
    cfg.field_presets = presets
    cfg.default_preset = default
    return cfg


def test_none_falls_back_to_default_preset() -> None:
    cfg = _config(
        {
            "id": ["id"],
            "ref": ["id", "title"],
            "full": "*",
        },
        default="id",
    )
    assert resolve_field_projection(None, cfg) == {"id"}


def test_default_preset_full_returns_none() -> None:
    cfg = _config({"full": "*"}, default="full")
    assert resolve_field_projection(None, cfg) is None


def test_preset_name_string() -> None:
    cfg = _config({"id": ["id"], "ref": ["id", "title"]}, default="id")
    assert resolve_field_projection("ref", cfg) == {"id", "title"}


def test_preset_full_returns_none_for_skip_projection() -> None:
    cfg = _config({"id": ["id"], "full": "*"}, default="id")
    assert resolve_field_projection("full", cfg) is None


def test_native_list() -> None:
    cfg = _config({"id": ["id"]}, default="id")
    assert resolve_field_projection(["id", "title", "bpm"], cfg) == {"id", "title", "bpm"}


def test_json_encoded_list_string() -> None:
    """Regression: Claude Code stdio shim stringifies list args.

    Prior to v1.0.13 the JSON-string was treated as a preset name lookup,
    fell through to the default preset, and the caller's projection was
    silently ignored.
    """
    cfg = _config({"id": ["id"]}, default="id")
    result = resolve_field_projection('["id", "title"]', cfg)
    assert result == {"id", "title"}


def test_csv_string() -> None:
    cfg = _config({"id": ["id"]}, default="id")
    assert resolve_field_projection("id,title,bpm", cfg) == {"id", "title", "bpm"}


def test_csv_with_whitespace() -> None:
    cfg = _config({"id": ["id"]}, default="id")
    assert resolve_field_projection("id, title, bpm", cfg) == {"id", "title", "bpm"}


def test_empty_string_returns_none() -> None:
    """Defensive: don't return an empty set from a typo — fall back to full."""
    cfg = _config({"id": ["id"]}, default="id")
    assert resolve_field_projection("", cfg) is None


def test_empty_list_returns_none() -> None:
    cfg = _config({"id": ["id"]}, default="id")
    assert resolve_field_projection([], cfg) is None


def test_list_with_blank_entries_filtered() -> None:
    cfg = _config({"id": ["id"]}, default="id")
    assert resolve_field_projection(["id", "", "title", "  "], cfg) == {"id", "title"}


def test_malformed_json_falls_through_to_csv() -> None:
    """``"[id"`` (broken JSON) should not crash the dispatcher.

    Falls through to CSV split — caller still gets a sensible projection
    rather than a 500 error from a typo.
    """
    cfg = _config({"id": ["id"]}, default="id")
    # ``"[id"`` is invalid JSON; CSV parse yields a single field named "[id"
    # which is harmless (model_dump(include={"[id"}) yields empty dict).
    result = resolve_field_projection("[id", cfg)
    assert result == {"[id"}
