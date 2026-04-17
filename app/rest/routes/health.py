"""GET /api/health."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.rest.schemas import HealthResponse
from app.rest.state import ApiRuntimeState

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    runtime: ApiRuntimeState = request.app.state.runtime
    tool_count = 0
    if runtime.mcp is not None and runtime.mcp_ready:
        tools = await runtime.mcp.list_tools()
        tool_count = len(tools)
    return HealthResponse(
        status="ok" if runtime.mcp_ready else "degraded",
        mcp_ready=runtime.mcp_ready,
        tool_count=tool_count,
        degraded_reason=runtime.degraded_reason,
    )
