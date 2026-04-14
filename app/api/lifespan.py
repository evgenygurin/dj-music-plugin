"""Lifespan management for the FastAPI wrapper."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.state import get_runtime
from app.clients.ym.adapter import YandexMusicAdapter
from app.clients.ym.factory import build_ym_client
from app.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


@asynccontextmanager
async def api_lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Start the MCP lifespan and the dedicated HTTP providers."""
    runtime = get_runtime(app)

    ym_client = build_ym_client()
    adapter = YandexMusicAdapter(ym_client)
    registry = ProviderRegistry()
    registry.register(adapter, default=True)

    runtime.ym_client = ym_client
    runtime.provider_registry = registry  # type: ignore[attr-defined]

    try:
        async with runtime.mcp_app.router.lifespan_context(runtime.mcp_app):
            runtime.mcp_ready = True
            logger.info("MCP server started — tool execution enabled")
            yield
    except Exception:
        logger.exception(
            "MCP lifespan failed (DB unreachable?) — "
            "tool discovery works, but tool execution disabled"
        )
        runtime.mcp_ready = False
        yield
    finally:
        runtime.mcp_ready = False
        await registry.close_all()
        runtime.ym_client = None
