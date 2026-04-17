"""Tests for transforms composition (Task 20)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.server.transforms import (
    ALWAYS_VISIBLE_TOOLS,
    build_pre_constructor_transforms,
    register_post_constructor_transforms,
)


def test_always_visible_list_matches_blueprint() -> None:
    assert ALWAYS_VISIBLE_TOOLS == (
        "entity_list",
        "entity_get",
        "entity_create",
        "entity_aggregate",
        "provider_read",
        "provider_search",
        "transition_score_pool",
        "sequence_optimize",
        "unlock_namespace",
    )


def test_pre_constructor_transforms_include_bm25() -> None:
    transforms = build_pre_constructor_transforms()
    names = [type(t).__name__ for t in transforms]
    assert "BM25SearchTransform" in names


def test_register_post_constructor_transforms_invokes_prompts_and_resources() -> None:
    mcp = MagicMock()
    with (
        patch("app.server.transforms.PromptsAsTools") as PAT,
        patch("app.server.transforms.ResourcesAsTools") as RAT,
    ):
        register_post_constructor_transforms(mcp)
    PAT.assert_called_once_with(mcp)
    RAT.assert_called_once_with(mcp)
    assert mcp.add_transform.call_count >= 2


def test_code_mode_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("DJ_MCP_CODE_MODE", raising=False)
    mcp = MagicMock()
    with (
        patch("app.server.transforms.PromptsAsTools"),
        patch("app.server.transforms.ResourcesAsTools"),
        patch("app.server.transforms.CodeMode") as CM,
    ):
        register_post_constructor_transforms(mcp)
    CM.assert_not_called()


def test_code_mode_enabled_by_flag(monkeypatch) -> None:
    monkeypatch.setenv("DJ_MCP_CODE_MODE", "1")
    mcp = MagicMock()
    with (
        patch("app.server.transforms.PromptsAsTools"),
        patch("app.server.transforms.ResourcesAsTools"),
        patch("app.server.transforms.CodeMode") as CM,
    ):
        register_post_constructor_transforms(mcp)
    # CodeMode may be None if experimental module unavailable; the patch
    # replaces it unconditionally so the branch executes.
    CM.assert_called_once_with(mcp)
