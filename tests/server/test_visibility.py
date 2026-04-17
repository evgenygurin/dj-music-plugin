"""Tests for visibility policy (Task 21)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.server.visibility import (
    DISABLED_NAMESPACE_TAGS,
    KNOWN_NAMESPACES,
    apply_visibility_policy,
)


def test_disabled_namespace_tags_matches_blueprint() -> None:
    assert frozenset(
        {
            "namespace:crud:destructive",
            "namespace:provider:write",
            "namespace:sync",
        }
    ) == DISABLED_NAMESPACE_TAGS


def test_known_namespaces_matches_blueprint() -> None:
    assert frozenset({"crud:destructive", "provider:write", "sync"}) == KNOWN_NAMESPACES


def test_apply_visibility_calls_disable_with_all_tags() -> None:
    mcp = MagicMock()
    apply_visibility_policy(mcp)
    mcp.disable.assert_called_once()
    # The positional/keyword args must carry exactly the three namespace tags.
    call = mcp.disable.call_args
    passed_tags = call.kwargs.get("tags")
    assert passed_tags is not None
    assert set(passed_tags) == set(DISABLED_NAMESPACE_TAGS)
