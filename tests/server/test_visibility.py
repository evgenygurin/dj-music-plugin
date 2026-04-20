"""Tests for visibility policy (Task 21)."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.server.visibility import (
    DISABLED_NAMESPACE_TAGS,
    KNOWN_NAMESPACES,
    apply_visibility_policy,
)


def test_disabled_namespace_tags_are_empty_by_default() -> None:
    # All namespaces are visible out of the box: Claude Code does not
    # always honour ``notifications/tools/list_changed`` mid-session,
    # so unlocking at runtime would not reveal previously-hidden tools.
    assert frozenset() == DISABLED_NAMESPACE_TAGS


def test_known_namespaces_matches_blueprint() -> None:
    # ``ui:read`` added in v1.0.3 for Prefab Apps UI tools (``app/tools/ui/``).
    assert frozenset({"crud:destructive", "provider:write", "sync", "ui:read"}) == KNOWN_NAMESPACES


def test_apply_visibility_calls_disable_with_all_tags() -> None:
    mcp = MagicMock()
    apply_visibility_policy(mcp)
    mcp.disable.assert_called_once()
    # The positional/keyword args must carry exactly the disabled tag set
    # (empty by default — see ``test_disabled_namespace_tags_are_empty_by_default``).
    call = mcp.disable.call_args
    passed_tags = call.kwargs.get("tags")
    assert passed_tags is not None
    assert set(passed_tags) == set(DISABLED_NAMESPACE_TAGS)
