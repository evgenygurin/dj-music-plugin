"""Tool discovery endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.openapi import TOOL_SCHEMA_RESPONSES
from app.api.schemas import ToolCategoryLiteral, ToolInfo, ToolListResponse
from app.api.state import get_runtime

router = APIRouter()


@router.get("/api/tools", tags=["discovery"], response_model=ToolListResponse)
async def list_tools(
    request: Request,
    tag: ToolCategoryLiteral | None = Query(
        default=None,
        description="Фильтр по категории tools (значения соответствуют ToolCategory enum).",
    ),
) -> ToolListResponse:
    """Список всех MCP tools с inputSchema."""
    runtime = get_runtime(request)
    tools = runtime.tool_registry.list_tools(tag=tag)
    return ToolListResponse(total=len(tools), tools=[ToolInfo(**tool) for tool in tools])


@router.get("/api/tools/{tool_name}", tags=["discovery"], response_model=ToolInfo)
async def get_tool(tool_name: str, request: Request) -> ToolInfo:
    """Метаданные и inputSchema конкретного MCP tool."""
    runtime = get_runtime(request)
    tool = runtime.tool_registry.get_tool(tool_name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return ToolInfo(**tool)


@router.get("/api/tools/{tool_name}/schema", tags=["discovery"], responses=TOOL_SCHEMA_RESPONSES)
async def get_tool_schema(tool_name: str, request: Request) -> dict[str, Any]:
    """JSON Schema параметров tool (inputSchema) — удобно для генерации форм."""
    runtime = get_runtime(request)
    schema = runtime.tool_registry.get_schema(tool_name)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return schema
