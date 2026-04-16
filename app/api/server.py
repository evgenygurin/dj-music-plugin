"""FastAPI wrapper exposing FastMCP server over HTTP with Swagger/OpenAPI docs.

Usage:
    uv run --extra http uvicorn app.api.server:api --host 0.0.0.0 --port 8000 --reload

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json
MCP (native): POST http://localhost:8000/mcp
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.lifespan import api_lifespan
from app.api.openapi import API_DESCRIPTION, OPENAPI_TAGS, project_version
from app.api.routes.discovery import router as discovery_router
from app.api.routes.execution import router as execution_router
from app.api.routes.health import router as health_router
from app.api.state import build_api_runtime
from app.server import mcp

api = FastAPI(
    title="DJ Music Plugin — MCP API",
    description=API_DESCRIPTION,
    version=project_version(),
    openapi_tags=OPENAPI_TAGS,
    lifespan=api_lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

api.state.runtime = build_api_runtime(mcp)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

api.include_router(health_router)
api.include_router(discovery_router)
api.include_router(execution_router)

api.mount("/mcp", api.state.runtime.mcp_app)
