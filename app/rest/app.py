"""FastAPI app factory — thin wrapper over MCP."""

from __future__ import annotations

import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.rest.lifespan import rest_lifespan
from app.rest.routes import discovery, execution, health

_CORS_ENV_VAR = "DJ_MCP_CORS_ALLOW_ORIGINS"
_CORS_DEFAULT: tuple[str, ...] = ("http://localhost:3000",)


def _cors_origins() -> list[str]:
    """Return the trusted origins list.

    Reads ``DJ_MCP_CORS_ALLOW_ORIGINS`` directly from the environment so the
    module-level ``api = build_rest_app()`` below does not eagerly instantiate
    the full ``Settings`` aggregate (database, yandex, …). An unrelated env
    parsing error in those sub-settings would otherwise abort REST import.

    Accepts both CSV and JSON-array shapes:
        DJ_MCP_CORS_ALLOW_ORIGINS="http://localhost:3000,https://panel.vercel.app"
        DJ_MCP_CORS_ALLOW_ORIGINS='["http://localhost:3000","https://panel.vercel.app"]'
    """
    raw = os.environ.get(_CORS_ENV_VAR, "").strip()
    if not raw:
        return list(_CORS_DEFAULT)
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_rest_app() -> FastAPI:
    app = FastAPI(
        title="DJ Music Plugin v2 — REST",
        version="2.0.0",
        lifespan=rest_lifespan,
    )
    # Trusted origins come from ``DJ_MCP_CORS_ALLOW_ORIGINS`` (CSV or JSON
    # array). Default is local panel dev only. We intentionally do NOT
    # accept a broad wildcard like ``https://*.vercel.app``: with
    # ``allow_credentials=True`` that would trust every Vercel-hosted site,
    # letting any visitor's browser issue cross-origin calls to this API.
    # Deployers opt in explicitly to production origins (panel, inspector, …).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
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
