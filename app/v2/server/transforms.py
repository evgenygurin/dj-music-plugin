"""FastMCP v3 transforms.

- ``BM25SearchTransform`` — keeps a fixed set of core tools always visible,
  ranks the rest via BM25 on client queries.
- ``PromptsAsTools`` — exposes prompts as tools for tool-only clients.
- ``ResourcesAsTools`` — exposes resources as tools for tool-only clients.
- ``CodeMode`` — optional zero-round-trip pipeline mode, gated by
  ``DJ_MCP_CODE_MODE`` env flag.

Split by lifecycle:

- ``build_pre_constructor_transforms()`` returns transforms that must be
  passed into ``FastMCP(transforms=...)`` BEFORE the server scans tools.
- ``register_post_constructor_transforms(mcp)`` wires transforms that
  need a fully constructed ``mcp`` instance.
"""

from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.transforms import PromptsAsTools, ResourcesAsTools
from fastmcp.server.transforms.search import BM25SearchTransform

try:  # pragma: no cover - optional experimental module
    from fastmcp.experimental.transforms.code_mode import (
        CodeMode,  # type: ignore[import-not-found]
    )
except ImportError:  # pragma: no cover
    CodeMode = None  # type: ignore[assignment,misc]


# Always-visible tools — everything else is BM25-ranked per client query.
ALWAYS_VISIBLE_TOOLS: tuple[str, ...] = (
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


def build_pre_constructor_transforms() -> list[Any]:
    """Transforms that need to be handed to the ``FastMCP(transforms=...)`` arg."""
    return [
        BM25SearchTransform(
            always_visible=list(ALWAYS_VISIBLE_TOOLS),
            max_results=8,
        ),
    ]


def register_post_constructor_transforms(mcp: FastMCP) -> None:
    """Register transforms that need the fully-constructed ``mcp`` instance.

    ``PromptsAsTools`` and ``ResourcesAsTools`` expose prompts/resources as
    tools for tool-only clients. ``CodeMode`` is experimental and disabled
    by default.
    """
    mcp.add_transform(PromptsAsTools(mcp))
    mcp.add_transform(ResourcesAsTools(mcp))
    if os.getenv("DJ_MCP_CODE_MODE", "0") == "1" and CodeMode is not None:
        mcp.add_transform(CodeMode(mcp))
