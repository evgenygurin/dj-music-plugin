"""FastAPI app factory — thin wrapper over MCP."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.rest.lifespan import rest_lifespan
from app.rest.routes import discovery, execution, health


def build_rest_app() -> FastAPI:
    app = FastAPI(
        title="DJ Music Plugin v2 — REST",
        version="2.0.0",
        lifespan=rest_lifespan,
    )
    settings = get_settings()
    # Trusted origins come from ``DJ_MCP_CORS_ALLOW_ORIGINS`` (comma-separated)
    # or default to ``["http://localhost:3000"]``. We intentionally do NOT
    # accept a broad wildcard like ``https://*.vercel.app``: with
    # ``allow_credentials=True`` that would trust every Vercel-hosted site,
    # letting any visitor's browser issue cross-origin calls to this API.
    # Deployers opt in explicitly to production origins (panel, inspector, …).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.mcp.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "Authorization",
            "Content-Type",
        ],
        expose_headers=["mcp-session-id"],
    )
    app.include_router(health.router)
    app.include_router(discovery.router)
    app.include_router(execution.router)
    return app


api = build_rest_app()
