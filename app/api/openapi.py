"""OpenAPI metadata for the FastAPI wrapper."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def project_version() -> str:
    """Read version from the repository pyproject.toml."""
    try:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
        return str(data.get("project", {}).get("version", "0.0.0"))
    except Exception:
        return "0.0.0"


OPENAPI_TAGS: list[dict[str, str]] = [
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

API_DESCRIPTION = (
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
)

CALL_EXAMPLES: dict[str, dict[str, Any]] = {
    "list_tracks": {
        "summary": "list_tracks — первые 10 треков",
        "value": {"arguments": {"limit": 10}},
    },
    "search_library": {
        "summary": "search_library — найти треки по запросу",
        "value": {"arguments": {"query": "techno", "entity": "tracks", "limit": 20}},
    },
    "ym_get_tracks": {
        "summary": "ym_get_tracks — batch fetch по YM IDs",
        "value": {"arguments": {"track_ids": ["54486493", "55516369"]}},
    },
    "commit_set_version": {
        "summary": "commit_set_version — сохранить курируемый ИИ порядок треков",
        "value": {
            "arguments": {
                "name": "Peak Hour 60",
                "track_ids": [101, 102, 103],
                "template": "peak_hour_60",
            }
        },
    },
    "empty": {
        "summary": "get_library_stats — без аргументов",
        "value": {"arguments": {}},
    },
}

TOOL_SCHEMA_RESPONSES: dict[int | str, dict[str, Any]] = {
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

CALL_RESPONSES: dict[int | str, dict[str, Any]] = {
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
