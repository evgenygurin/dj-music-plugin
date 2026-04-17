"""FastAPI app factory — thin wrapper over MCP."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.rest.lifespan import rest_lifespan
from app.rest.routes import discovery, execution, health


def build_rest_app() -> FastAPI:
    app = FastAPI(
        title="DJ Music Plugin v2 — REST",
        version="2.0.0",
        lifespan=rest_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(discovery.router)
    app.include_router(execution.router)
    return app


api = build_rest_app()
