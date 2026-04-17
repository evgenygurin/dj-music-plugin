"""FastAPI lifespan — builds the MCP server, sets it on app.state."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.rest.state import ApiRuntimeState

log = logging.getLogger(__name__)


@asynccontextmanager
async def rest_lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = ApiRuntimeState()
    app.state.runtime = state
    try:
        from app.server.app import build_mcp_server

        state.mcp = build_mcp_server()
        state.mcp_ready = True
        log.info("REST wrapper: MCP ready")
    except Exception as exc:  # pragma: no cover - degraded mode
        state.degraded_reason = f"{type(exc).__name__}: {exc}"
        log.exception("REST wrapper: MCP build failed, entering degraded mode")
    yield
