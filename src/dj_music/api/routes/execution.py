"""Tool execution endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastmcp.exceptions import NotFoundError, ToolError, ValidationError

from dj_music.api.openapi import CALL_EXAMPLES, CALL_RESPONSES
from dj_music.api.schemas import ToolCallRequest, ToolCallResponse
from dj_music.api.state import get_runtime

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/api/tools/{tool_name}/call",
    tags=["execution"],
    response_model=ToolCallResponse,
    responses=CALL_RESPONSES,
)
async def call_tool(
    tool_name: str,
    request: Request,
    payload: ToolCallRequest = Body(..., openapi_examples=CALL_EXAMPLES),
) -> ToolCallResponse:
    """Вызвать MCP tool по имени."""
    runtime = get_runtime(request)
    if not runtime.mcp_ready:
        raise HTTPException(
            status_code=503,
            detail="MCP server not ready — DB may be unreachable",
        )

    if runtime.tool_registry.get_tool(tool_name) is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    try:
        result = await runtime.mcp.call_tool(tool_name, arguments=payload.arguments)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ToolError as exc:
        logger.warning("Tool '%s' execution error: %s", tool_name, exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error calling tool '%s'", tool_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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

    return ToolCallResponse(
        tool_name=tool_name,
        content=content,
        structured_content=structured,
        is_error=False,
    )
