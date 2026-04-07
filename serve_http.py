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
import tomllib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.server import mcp

logger = logging.getLogger(__name__)


def _project_version() -> str:
    """Read version from pyproject.toml so OpenAPI doesn't drift from source.

    Falls back to "0.0.0" if pyproject.toml is missing or unreadable.
    """
    try:
        pyproject = Path(__file__).parent / "pyproject.toml"
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
        return str(data.get("project", {}).get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


# ── Static tool discovery (no DB required) ──────────


def _discover_tools_static() -> list[dict[str, Any]]:
    """Extract tool metadata from filesystem at import time.

    Uses FastMCP's FileSystemProvider discovery to read @tool decorated
    functions without starting the full MCP server (no DB connection needed).
    """
    from fastmcp.server.providers.filesystem_discovery import discover_and_import
    from fastmcp.tools import Tool

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
    """Request body for calling an MCP tool.

    Per-tool schema is available via ``GET /api/tools/{name}/schema``.
    Concrete invocation examples are attached at the operation level via
    ``Body(openapi_examples=...)`` — see ``call_tool`` below.
    """

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Tool arguments as key-value pairs. Shape depends on the tool — "
            "fetch the per-tool JSON Schema from `GET /api/tools/{name}/schema`."
        ),
    )

    # Schema-level example: Swagger UI's static "Example Value" box uses the
    # json-schema `example` key. Without it, it auto-generates the infamous
    # `additionalProp1: {}` placeholder from `additionalProperties: true`.
    model_config = {
        "json_schema_extra": {
            "example": {"arguments": {"limit": 10}},
        }
    }


# Concrete request examples surfaced by Swagger UI's "Example Value" dropdown.
# Operation-level openapi_examples (vs model json_schema_extra) is the only
# place FastAPI wires into the request body examples picker.
_CALL_EXAMPLES: dict[str, dict[str, Any]] = {
    "list_tracks": {
        "summary": "list_tracks — первые 10 треков",
        "value": {"arguments": {"limit": 10}},
    },
    "search": {
        "summary": "search — найти треки по запросу",
        "value": {"arguments": {"query": "techno", "entity": "tracks", "limit": 20}},
    },
    "filter_tracks": {
        "summary": "filter_tracks — по BPM и тональности",
        "value": {
            "arguments": {
                "bpm_min": 125,
                "bpm_max": 132,
                "key": "8A",
                "limit": 20,
            }
        },
    },
    "ym_get_tracks": {
        "summary": "ym_get_tracks — batch fetch по YM IDs",
        "value": {"arguments": {"track_ids": ["54486493", "55516369"]}},
    },
    "build_set": {
        "summary": "build_set — собрать сет из плейлиста",
        "value": {
            "arguments": {
                "playlist_id": 1,
                "name": "Peak Hour 60",
                "template": "peak_hour_60",
                "algorithm": "ga",
            }
        },
    },
    "empty": {
        "summary": "get_library_stats — без аргументов",
        "value": {"arguments": {}},
    },
}


class ToolCallResponse(BaseModel):
    """Response from an MCP tool call."""

    tool_name: str
    content: list[dict[str, Any]] = Field(default_factory=list)
    structured_content: dict[str, Any] | None = None
    is_error: bool = False

    model_config = {
        "json_schema_extra": {
            "example": {
                "tool_name": "list_tracks",
                "content": [
                    {
                        "type": "text",
                        "text": '{"items":[{"id":146,"title":"Soul Spiritism","bpm":129.2}],"total":1}',
                    }
                ],
                "structured_content": {
                    "items": [
                        {
                            "id": 146,
                            "title": "Soul Spiritism",
                            "artist_names": ["DRVSH"],
                            "bpm": 129.2,
                            "key_camelot": "6A",
                            "duration_ms": 435000,
                        }
                    ],
                    "total": 1,
                    "next_cursor": None,
                },
                "is_error": False,
            }
        }
    }


class ToolInfo(BaseModel):
    """MCP tool metadata."""

    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    annotations: dict[str, Any] | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    timeout: float | None = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "list_tracks",
                "description": "List tracks with cursor pagination and optional BPM filter",
                "tags": ["core"],
                "annotations": {"readOnlyHint": True},
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 50},
                        "cursor": {"type": "string", "nullable": True},
                        "bpm_min": {"type": "number", "nullable": True},
                        "bpm_max": {"type": "number", "nullable": True},
                    },
                },
                "timeout": None,
            }
        }
    }


class ToolListResponse(BaseModel):
    """List of all registered MCP tools."""

    total: int
    tools: list[ToolInfo]

    model_config = {
        "json_schema_extra": {
            "example": {
                "total": 50,
                "tools": [
                    {
                        "name": "list_tracks",
                        "description": "List tracks with cursor pagination",
                        "tags": ["core"],
                        "annotations": {"readOnlyHint": True},
                        "input_schema": {"type": "object", "properties": {}},
                        "timeout": None,
                    }
                ],
            }
        }
    }


# ── Lifespan ────────────────────────────────────────

mcp_app = mcp.http_app(path="/")
_mcp_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Start MCP server lifespan (DB, YM client, analyzers, cache).

    If MCP lifespan fails (e.g., DB unreachable), the REST API still works
    for tool discovery. Only /api/tools/{name}/call requires a running MCP server.
    """
    global _mcp_ready
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

# OpenAPI top-level tags — Swagger UI groups operations under these and shows
# the descriptions inline, which is much more useful than a single big
# markdown table buried in the description.
_OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "system", "description": "Health check и операционные данные."},
    {
        "name": "discovery",
        "description": "Поиск, листинг и схема MCP tools (без вызова).",
    },
    {
        "name": "execution",
        "description": "Универсальный POST /api/tools/{name}/call для вызова любого MCP tool.",
    },
    {
        "name": "mcp",
        "description": (
            "Нативный MCP StreamableHTTP transport, смонтирован на /mcp. "
            "Используется AI-клиентами; не описывается в этом OpenAPI."
        ),
    },
]

api = FastAPI(
    title="DJ Music Plugin — MCP API",
    description=(
        "MCP-сервер для управления DJ techno библиотекой, построения "
        "оптимизированных сетов и интеграции с Яндекс Музыкой.\n\n"
        "## Транспорты\n\n"
        "| Транспорт | URL | Описание |\n"
        "|-----------|-----|----------|\n"
        "| MCP (StreamableHTTP) | `POST /mcp` | Нативный MCP-протокол (не в OpenAPI) |\n"
        "| REST API | `/api/*` | HTTP-обёртка для Swagger |\n\n"
        "REST API — тонкий gateway над `mcp.call_tool()`. Все 50 tools "
        "вызываются через универсальный `POST /api/tools/{name}/call`. "
        "Схема `arguments` per-tool — через `GET /api/tools/{name}/schema`."
    ),
    version=_project_version(),
    openapi_tags=_OPENAPI_TAGS,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────


@api.get(
    "/api/health",
    tags=["system"],
    responses={
        200: {
            "description": "Сервер работает; tools_discovered = число обнаруженных tools.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "tools_discovered": 50,
                        "mcp_ready": True,
                    }
                }
            },
        }
    },
)
def health() -> dict[str, str | int | bool]:
    """Проверка работоспособности сервера."""
    return {
        "status": "ok",
        "tools_discovered": len(_tools_cache),
        "mcp_ready": _mcp_ready,
    }


# ── Tool Discovery ──────────────────────────────────


# Tag query param uses Literal of all real ToolCategory values so Swagger UI
# renders a dropdown instead of a free-form text field. Keeping this in sync
# with ToolCategory is mechanical: extend the enum in app/mcp/tools/_shared
# and the Literal updates here on next reload.
_ToolCategoryLiteral = Literal[
    "core",
    "sets",
    "delivery",
    "discovery",
    "curation",
    "sync",
    "ym",
    "admin",
    "audio",
    "atomic",
]


@api.get("/api/tools", tags=["discovery"], response_model=ToolListResponse)
async def list_tools(
    tag: _ToolCategoryLiteral | None = Query(
        default=None,
        description="Фильтр по категории tools (значения соответствуют ToolCategory enum).",
    ),
) -> ToolListResponse:
    """Список всех MCP tools с inputSchema.

    Опционально фильтрует по категории — например `?tag=core`, `?tag=sets`,
    `?tag=ym`. Без `tag` возвращает все 50 tools.
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


_TOOL_SCHEMA_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "JSON Schema (Draft 7) для аргументов tool.",
        "content": {
            "application/json": {
                "example": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "description": "Page size",
                        },
                        "cursor": {"type": "string", "nullable": True},
                        "bpm_min": {"type": "number", "nullable": True},
                        "bpm_max": {"type": "number", "nullable": True},
                    },
                    "required": [],
                }
            }
        },
    },
    404: {
        "description": "Tool not found",
        "content": {"application/json": {"example": {"detail": "Tool 'unknown_tool' not found"}}},
    },
}


@api.get("/api/tools/{tool_name}/schema", tags=["discovery"], responses=_TOOL_SCHEMA_RESPONSES)
async def get_tool_schema(tool_name: str) -> dict[str, Any]:
    """JSON Schema параметров tool (inputSchema) — удобно для генерации форм."""
    for t in _tools_cache:
        if t["name"] == tool_name:
            return t["input_schema"]
    raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")


# ── Tool Execution ──────────────────────────────────

_CALL_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {
        "description": "Tool not found",
        "content": {
            "application/json": {
                "example": {"detail": "Tool 'unknown_tool' not found"},
            }
        },
    },
    422: {
        "description": (
            "Tool execution failed (invalid arguments или domain error). "
            "В production режиме (`mask_error_details=True`) сообщение скрыто. "
            "Полный traceback всегда логгируется на сервере через ErrorHandlingMiddleware."
        ),
    },
    503: {
        "description": "MCP server lifespan не запустился (БД недоступна).",
        "content": {
            "application/json": {
                "example": {"detail": "MCP server not ready — DB may be unreachable"},
            }
        },
    },
}


@api.post(
    "/api/tools/{tool_name}/call",
    tags=["execution"],
    response_model=ToolCallResponse,
    responses=_CALL_RESPONSES,
)
async def call_tool(
    tool_name: str,
    request: ToolCallRequest = Body(..., openapi_examples=_CALL_EXAMPLES),
) -> ToolCallResponse:
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

    structured: dict[str, Any] | None = None
    raw_structured = getattr(result, "structured_content", None)
    if raw_structured:
        structured = (
            raw_structured if isinstance(raw_structured, dict) else {"data": raw_structured}
        )

    # FastMCP raises on error rather than returning ToolResult.is_error, so by
    # the time we get here is_error is always False. We keep the field in the
    # response model for forward compatibility but never set it from a missing
    # attribute.
    return ToolCallResponse(
        tool_name=tool_name,
        content=content,
        structured_content=structured,
        is_error=False,
    )


# ── MCP Transport (native) ─────────────────────────

api.mount("/mcp", mcp_app)
