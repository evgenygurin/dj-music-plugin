"""Composition root for the v2 MCP server.

Order (load-bearing):

1. ``bootstrap_observability()`` — Sentry/OTEL init (idempotent).
2. ``FastMCP(providers=[FileSystemProvider(root=app/v2)], transforms=pre,
   lifespan=build_server_lifespan(), sampling_handler=build_sampling_handler())``.
3. ``register_post_constructor_transforms(mcp)`` — PromptsAsTools,
   ResourcesAsTools, optional CodeMode.
4. ``register_middleware(mcp)`` — 16 middleware in blueprint §11 order.
5. ``apply_visibility_policy(mcp)`` — disable 3 namespace tags at startup.

Violating the order hides bugs (transforms see wrong tool set, visibility
ignored by middleware, etc.).

Public entrypoints:

- ``build_mcp_server()`` — production composition.
- ``build_mcp_app_for_tests(**overrides)`` — same composition with knobs for
  tests (disable middleware, skip transforms, inject overrides).

FastMCP v3 API used:

- ``FastMCP.add_provider(FileSystemProvider)`` — constructor ``providers=``.
- ``FastMCP.add_transform(transform)``.
- ``FastMCP.add_middleware(middleware)``.
- ``FastMCP.disable(tags={...})``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.providers.filesystem import FileSystemProvider

from app.v2.server.lifespan import build_server_lifespan
from app.v2.server.middleware import ALL_MIDDLEWARE
from app.v2.server.observability import bootstrap_observability
from app.v2.server.sampling import build_sampling_handler
from app.v2.server.transforms import (
    build_pre_constructor_transforms,
    register_post_constructor_transforms,
)
from app.v2.server.visibility import apply_visibility_policy

log = logging.getLogger(__name__)


def _v2_root() -> Path:
    # ``app/v2/server/app.py`` → ``app/v2``
    return Path(__file__).resolve().parent.parent


def register_middleware(mcp: FastMCP) -> None:
    """Register all 16 middleware in blueprint §11 order."""
    for cls in ALL_MIDDLEWARE:
        mcp.add_middleware(cls())


def build_mcp_server() -> FastMCP:
    """Construct and wire up the full v2 MCP server."""
    bootstrap_observability()

    root = _v2_root()
    fsp_tools = FileSystemProvider(root=root / "tools")
    fsp_resources = FileSystemProvider(root=root / "resources")
    fsp_prompts = FileSystemProvider(root=root / "prompts")

    mcp = FastMCP(
        name="dj-music-v2",
        providers=[fsp_tools, fsp_resources, fsp_prompts],
        transforms=build_pre_constructor_transforms(),
        lifespan=build_server_lifespan(),
        sampling_handler=build_sampling_handler(),
    )

    # Post-constructor transforms scan already-registered tools/resources/prompts.
    register_post_constructor_transforms(mcp)

    # Middleware wraps the call chain; register AFTER transforms.
    register_middleware(mcp)

    # Visibility policy disables namespace tags for everyone at startup; run
    # LAST so middleware sees the full tool set.
    apply_visibility_policy(mcp)

    log.info("dj-music-v2 MCP server built")
    return mcp


async def build_mcp_app_for_tests(
    *,
    with_middleware: bool = True,
    with_transforms: bool = True,
    with_visibility: bool = True,
    with_lifespan: bool = False,
    with_sampling: bool = False,
    **_unused: Any,
) -> FastMCP:
    """Build a FastMCP server for integration tests.

    Defaults mirror production EXCEPT:

    - ``with_lifespan=False`` — tests rarely need a real DB engine.
    - ``with_sampling=False`` — tests stub sampling via in-memory client.

    All knobs can be toggled if a test specifically wants the real thing.
    """
    if with_transforms:
        bootstrap_observability()

    root = _v2_root()
    fsp_tools = FileSystemProvider(root=root / "tools")
    fsp_resources = FileSystemProvider(root=root / "resources")
    fsp_prompts = FileSystemProvider(root=root / "prompts")

    mcp = FastMCP(
        name="dj-music-v2-test",
        providers=[fsp_tools, fsp_resources, fsp_prompts],
        transforms=build_pre_constructor_transforms() if with_transforms else [],
        lifespan=build_server_lifespan() if with_lifespan else None,
        sampling_handler=build_sampling_handler() if with_sampling else None,
    )

    if with_transforms:
        register_post_constructor_transforms(mcp)
    if with_middleware:
        register_middleware(mcp)
    if with_visibility:
        apply_visibility_policy(mcp)

    return mcp
