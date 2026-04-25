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
        from app.registry.defaults import register_default_entities
        from app.registry.entity import EntityRegistry
        from app.server import _stateless_state
        from app.server.app import build_mcp_server
        from app.server.lifespan import build_server_lifespan

        state.mcp = build_mcp_server()
        # In-process REST does not enter MCP's own lifespan, so the
        # EntityRegistry is never seeded. Seed it here — idempotent.
        if not EntityRegistry.names():
            register_default_entities()

        # Enter the composed MCP lifespan ourselves and copy yielded keys
        # into the stateless fallback store so DI factories find them.
        composed = build_server_lifespan()
        async with composed(state.mcp) as ctx:
            if isinstance(ctx, dict):
                _stateless_state.update(ctx)
            state.mcp_ready = True
            log.info("REST wrapper: MCP ready (lifespan keys: %s)", sorted(ctx or {}))
            try:
                yield
            finally:
                _stateless_state.clear()
        return
    except Exception as exc:  # pragma: no cover - degraded mode
        state.degraded_reason = f"{type(exc).__name__}: {exc}"
        log.exception("REST wrapper: MCP build failed, entering degraded mode")
    yield
