"""FastMCP server composition root."""

from __future__ import annotations

import logging
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider

from dj_music.core.config import settings
from dj_music.core.observability_setup import setup_observability
from dj_music.di.lifespans import build_server_lifespan
from dj_music.di.middleware import register_middleware
from dj_music.di.sampling import build_sampling_handler
from dj_music.di.transforms import (
    build_pre_constructor_transforms,
    register_post_constructor_transforms,
)
from dj_music.di.visibility import apply_visibility_policy

logger = logging.getLogger(__name__)


def build_mcp_server() -> FastMCP:
    """Build the production FastMCP server instance."""
    observability = setup_observability(logger)
    sampling_handler, sampling_handler_behavior = build_sampling_handler(logger)

    # src/dj_music/ — FileSystemProvider auto-discovers tools/resources/prompts
    mcp_dir = Path(__file__).resolve().parents[1]
    server_transforms = build_pre_constructor_transforms(logger)

    mcp = FastMCP(
        name=settings.server_name,
        instructions=(
            "DJ techno music library management, set building, "
            "and Yandex Music integration. "
            "Use unlock_tools to access hidden tool categories."
        ),
        providers=[FileSystemProvider(mcp_dir)],
        transforms=server_transforms,
        lifespan=build_server_lifespan(),
        list_page_size=settings.pagination_size,
        on_duplicate="warn",
        mask_error_details=not settings.debug,
        sampling_handler=sampling_handler,
        sampling_handler_behavior=sampling_handler_behavior,
    )

    register_post_constructor_transforms(mcp, logger)
    register_middleware(
        mcp,
        error_callback=observability.error_callback,
        logger=logger,
    )
    apply_visibility_policy(mcp)
    return mcp
