"""FastMCP server composition root."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.providers import FileSystemProvider

from app.bootstrap.lifespans import build_server_lifespan
from app.bootstrap.middleware import register_middleware
from app.bootstrap.observability import setup_observability
from app.bootstrap.sampling import build_sampling_handler
from app.bootstrap.transforms import (
    build_pre_constructor_transforms,
    register_post_constructor_transforms,
)
from app.bootstrap.visibility import apply_visibility_policy
from app.config import settings

logger = logging.getLogger(__name__)


def _configure_background_task_environment() -> None:
    os.environ.setdefault("FASTMCP_DOCKET_URL", settings.docket_url)
    os.environ.setdefault("FASTMCP_DOCKET_CONCURRENCY", str(settings.docket_concurrency))


def build_mcp_server() -> FastMCP:
    """Build the production FastMCP server instance."""
    _configure_background_task_environment()
    observability = setup_observability(logger)
    sampling_handler, sampling_handler_behavior = build_sampling_handler(logger)

    mcp_dir = Path(__file__).resolve().parents[1] / "controllers"
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
