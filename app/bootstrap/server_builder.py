"""FastMCP server composition root.

Sampling: https://gofastmcp.com/servers/sampling — client LLM by default;
``sampling_handler`` + ``sampling_handler_behavior=\"fallback\"`` for provider fallback.
"""

from __future__ import annotations

import logging
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
from app.core.logging_config import configure_logging

logger = logging.getLogger(__name__)


def build_mcp_server() -> FastMCP:
    """Build the production FastMCP server instance."""
    configure_logging()
    observability = setup_observability(logger)
    sampling_handler = build_sampling_handler(logger)

    mcp_dir = Path(__file__).resolve().parents[1] / "controllers"
    server_transforms = build_pre_constructor_transforms(logger)

    mcp = FastMCP(
        name=settings.server_name,
        instructions=(
            "DJ techno music library management, set building, and platform integration.\n\n"
            "Core workflow: search_library → get_candidate_pool → update_set_draft → "
            "preview_draft → commit_draft.\n"
            "For automated builds: build_set(algorithm='greedy'|'ga').\n\n"
            "Start with dj_expert_session prompt to load knowledge base.\n"
            "Use unlock_tools(action='status') to see categories, "
            "unlock_tools(action='unlock', category='all') to enable all.\n\n"
            "Resources: library://snapshot for library state, "
            "reference:// for domain knowledge, session://set-draft for current draft."
        ),
        providers=[FileSystemProvider(mcp_dir)],
        transforms=server_transforms,
        lifespan=build_server_lifespan(),
        list_page_size=settings.pagination_size,
        on_duplicate="warn",
        mask_error_details=not settings.debug,
        sampling_handler=sampling_handler,
        sampling_handler_behavior="fallback",
    )

    register_post_constructor_transforms(mcp, logger)
    register_middleware(
        mcp,
        error_callback=observability.error_callback,
        logger=logger,
    )
    apply_visibility_policy(mcp)
    return mcp
