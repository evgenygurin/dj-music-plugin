"""Admin tools: tool visibility control and platform listing."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.controllers.dependencies import get_track_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ICON_ADMIN,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
)
from app.core.constants import Provider
from app.services.track_service import TrackService

# Categories that can be toggled at runtime. "core", "sets", "admin" are
# always visible, so the unlock controls only the hideable ones.
_TOGGLEABLE_CATEGORIES: frozenset[str] = frozenset(
    {
        ToolCategory.DELIVERY.value,
        ToolCategory.DISCOVERY.value,
        ToolCategory.CURATION.value,
        ToolCategory.SYNC.value,
        ToolCategory.YM.value,
        ToolCategory.AUDIO.value,
        ToolCategory.ATOMIC.value,
    }
)


def _resolve_categories(category: str) -> set[str]:
    tags = set(_TOGGLEABLE_CATEGORIES) if category == "all" else {category}
    invalid = tags - _TOGGLEABLE_CATEGORIES
    if invalid:
        raise ToolError(f"Unknown categories: {sorted(invalid)}")
    return tags


_VALID_UNLOCK_ACTIONS: frozenset[str] = frozenset({"unlock", "lock", "status"})


async def _build_status(ctx: Context | None) -> dict[str, Any]:
    """Compute the current per-session visibility state for toggleable tags.

    Visibility is rule-based in FastMCP: every ``enable_components`` /
    ``disable_components`` call appends a rule to ``_visibility_rules``
    in the session state. Later rules override earlier ones (the
    "Visibility transform" semantics).

    For each known toggleable category we walk the rule list in order
    and pick the **last** matching rule's ``enabled`` flag. Categories
    without any matching rule are reported as ``"default"`` so the user
    can see they fall back to whatever the server's static
    ``mcp.disable(tags=...)`` configured at startup.
    """
    rules: list[dict[str, Any]] = []
    if ctx is not None:
        rules = await ctx.get_state("_visibility_rules") or []

    effective: dict[str, str] = {}
    for category in sorted(_TOGGLEABLE_CATEGORIES):
        state = "default"
        for rule in rules:
            rule_tags = set(rule.get("tags") or [])
            if category in rule_tags:
                state = "enabled" if rule.get("enabled", True) else "disabled"
        effective[category] = state

    return {
        "action": "status",
        "toggleable_categories": sorted(_TOGGLEABLE_CATEGORIES),
        "effective": effective,
        "session_rules": rules,
    }


@tool(
    title="Unlock Tools",
    tags={ToolCategory.ADMIN.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_ADMIN,
    meta=TOOL_META,
)
@map_domain_errors
async def unlock_tools(
    action: str = "status",
    category: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Control which tool categories are visible in this session.

    ``action`` ∈ ``{unlock, lock, status}``. ``status`` returns the
    effective visibility per toggleable category for the current
    session — ``enabled`` / ``disabled`` / ``default`` (server default).
    """
    if action not in _VALID_UNLOCK_ACTIONS:
        raise ToolError(f"Unknown action: {action}. Valid: {sorted(_VALID_UNLOCK_ACTIONS)}")

    if action == "status":
        return await _build_status(ctx)

    # action ∈ {unlock, lock}
    if not category:
        raise ToolError(f"Category required for action={action}")
    if ctx is None:
        raise ToolError(f"Context required for {action}")

    tags = _resolve_categories(category)
    if action == "unlock":
        await ctx.enable_components(tags=tags)
        return {"action": "unlocked", "categories": sorted(tags)}
    await ctx.disable_components(tags=tags)
    return {"action": "locked", "categories": sorted(tags)}


@tool(
    title="List Platforms",
    tags={ToolCategory.ADMIN.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_ADMIN,
    meta=TOOL_META,
)
@map_domain_errors
async def list_platforms(
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> list[dict[str, Any]]:
    """List available music platforms and linked track counts."""
    db_platforms = await svc.get_platform_counts()
    return [
        {
            "platform": provider.value,
            "linked_tracks": db_platforms.get(provider.value, 0),
            "available": True,
        }
        for provider in Provider
    ]
