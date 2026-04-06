# serve_http.py
"""FastAPI wrapper exposing FastMCP server over HTTP with Swagger/OpenAPI docs.

Usage:
    uv run --extra http uvicorn serve_http:api --host 0.0.0.0 --port 8000 --reload

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json
MCP (native): POST http://localhost:8000/mcp
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.server import mcp

logger = logging.getLogger(__name__)

# ── Static tool discovery (no DB required) ──────────


def _discover_tools_static() -> list[dict[str, Any]]:
    """Extract tool metadata from filesystem at import time.

    Uses FastMCP's FileSystemProvider discovery to read @tool decorated
    functions without starting the full MCP server (no DB connection needed).
    """
    from fastmcp.server.providers.filesystem_discovery import discover_and_import
    from fastmcp.tools.base import Tool

    mcp_dir = Path(__file__).parent / "app" / "mcp"
    result = discover_and_import(mcp_dir)

    tools: list[dict[str, Any]] = []
    for _path, component in result.components:
        if not isinstance(component, Tool):
            continue
        tools.append(
            {
                "name": component.name,
                "description": component.description or "",
                "tags": sorted(component.tags) if component.tags else [],
                "annotations": (
                    component.annotations.model_dump(exclude_none=True)
                    if component.annotations
                    else None
                ),
                "input_schema": component.parameters or {},
                "timeout": component.timeout,
            }
        )

    tools.sort(key=lambda t: t["name"])
    return tools


_tools_cache: list[dict[str, Any]] = _discover_tools_static()
logger.info("Discovered %d MCP tools for OpenAPI docs", len(_tools_cache))

# ── Models ──────────────────────────────────────────


class ToolCallRequest(BaseModel):
    """Request body for calling an MCP tool."""

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool arguments as key-value pairs (see tool's inputSchema)",
    )


class ToolCallResponse(BaseModel):
    """Response from an MCP tool call."""

    tool_name: str
    content: list[dict[str, Any]] = Field(default_factory=list)
    structured_content: dict[str, Any] | None = None
    is_error: bool = False


class ToolInfo(BaseModel):
    """MCP tool metadata."""

    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    annotations: dict[str, Any] | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    timeout: float | None = None


class ToolListResponse(BaseModel):
    """List of all registered MCP tools."""

    total: int
    tools: list[ToolInfo]


# ── Lifespan ────────────────────────────────────────

mcp_app = mcp.http_app(path="/")
_mcp_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Start MCP server lifespan (DB, YM client, analyzers, cache).

    If MCP lifespan fails (e.g., DB unreachable), the REST API still works
    for tool discovery. Only /api/tools/{name}/call requires a running MCP server.
    """
    global _mcp_ready  # noqa: PLW0603
    try:
        async with mcp_app.router.lifespan_context(mcp_app):
            _mcp_ready = True
            logger.info("MCP server started — tool execution enabled")
            yield
    except Exception:
        logger.exception(
            "MCP lifespan failed (DB unreachable?) — "
            "tool discovery works, but tool execution disabled"
        )
        _mcp_ready = False
        yield


# ── FastAPI App ─────────────────────────────────────

api = FastAPI(
    title="DJ Music Plugin — MCP API",
    description=(
        "MCP-сервер для управления DJ techno библиотекой, построения "
        "оптимизированных сетов и интеграции с Яндекс Музыкой.\n\n"
        "## Транспорты\n\n"
        "| Транспорт | URL | Описание |\n"
        "|-----------|-----|----------|\n"
        "| MCP (StreamableHTTP) | `POST /mcp` | Нативный MCP-протокол |\n"
        "| REST API | `/api/*` | HTTP-обёртка для Swagger |\n\n"
        "## Категории tools\n\n"
        "| Категория | Кол-во | Описание |\n"
        "|-----------|--------|----------|\n"
        "| `core` | 10 | CRUD треков, плейлистов, сетов |\n"
        "| `sets` | 9 | Построение и анализ DJ-сетов |\n"
        "| `delivery` | 2 | Экспорт и доставка |\n"
        "| `discovery` | 5 | Поиск похожих треков, импорт |\n"
        "| `curation` | 5 | Классификация, аудит |\n"
        "| `sync` | 2 | Синхронизация с YM |\n"
        "| `ym` | 6 | Прямой доступ к YM API |\n"
        "| `admin` | 2 | Управление видимостью |\n"
        "| `audio` | 3 | Аудио-анализ (hidden) |\n"
        "| `atomic` | 4 | Атомарные операции (hidden) |\n"
    ),
    version="0.5.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────


@api.get("/api/health", tags=["system"])
def health() -> dict[str, str | int | bool]:
    """Проверка работоспособности сервера."""
    return {
        "status": "ok",
        "tools_discovered": len(_tools_cache),
        "mcp_ready": _mcp_ready,
    }


# ── Tool Discovery ──────────────────────────────────


@api.get("/api/tools", tags=["discovery"], response_model=ToolListResponse)
async def list_tools(tag: str | None = None) -> ToolListResponse:
    """Список всех MCP tools с inputSchema.

    Фильтрация по тегу: `?tag=core`, `?tag=sets`, `?tag=ym`
    """
    tools = _tools_cache
    if tag:
        tools = [t for t in tools if tag in t.get("tags", [])]
    return ToolListResponse(total=len(tools), tools=[ToolInfo(**t) for t in tools])


@api.get("/api/tools/{tool_name}", tags=["discovery"], response_model=ToolInfo)
async def get_tool(tool_name: str) -> ToolInfo:
    """Метаданные и inputSchema конкретного MCP tool."""
    for t in _tools_cache:
        if t["name"] == tool_name:
            return ToolInfo(**t)
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")


@api.get("/api/tools/{tool_name}/schema", tags=["discovery"])
async def get_tool_schema(tool_name: str) -> dict[str, Any]:
    """JSON Schema параметров tool (inputSchema) — удобно для генерации форм."""
    for t in _tools_cache:
        if t["name"] == tool_name:
            return t["input_schema"]
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")


# ── Tool Execution ──────────────────────────────────


@api.post(
    "/api/tools/{tool_name}/call",
    tags=["execution"],
    response_model=ToolCallResponse,
)
async def call_tool(tool_name: str, request: ToolCallRequest) -> ToolCallResponse:
    """Вызвать MCP tool по имени.

    Требует работающий MCP сервер (подключение к БД).
    Схема аргументов: `GET /api/tools/{tool_name}/schema`.
    """
    if not _mcp_ready:
        raise HTTPException(
            status_code=503,
            detail="MCP server not ready — DB may be unreachable",
        )

    found = any(t["name"] == tool_name for t in _tools_cache)
    if not found:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    try:
        result = await mcp.call_tool(tool_name, arguments=request.arguments)
    except Exception as e:
        logger.exception("Tool call failed: %s", tool_name)
        raise HTTPException(status_code=422, detail=str(e)) from e

    content: list[dict[str, Any]] = []
    if result.content:
        for item in result.content:
            content.append(item.model_dump(exclude_none=True))

    structured = None
    if hasattr(result, "structured_content") and result.structured_content:
        structured = (
            result.structured_content
            if isinstance(result.structured_content, dict)
            else {"data": result.structured_content}
        )

    return ToolCallResponse(
        tool_name=tool_name,
        content=content,
        structured_content=structured,
        is_error=result.is_error if hasattr(result, "is_error") else False,
    )


# ── MCP Transport (native) ─────────────────────────

api.mount("/mcp", mcp_app)
