"""Pydantic schemas for the FastAPI wrapper."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ToolCategoryLiteral = Literal[
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


class ToolCallRequest(BaseModel):
    """Request body for calling an MCP tool."""

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Tool arguments as key-value pairs. Shape depends on the tool — "
            "fetch the per-tool JSON Schema from `GET /api/tools/{name}/schema`."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {"arguments": {"limit": 10}},
        }
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
