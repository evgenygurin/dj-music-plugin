"""POST /api/tools/{name}/call."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.v2.rest.schemas import ToolCallRequest, ToolCallResponse

router = APIRouter(prefix="/api/tools", tags=["execution"])


def _as_jsonable(result: object) -> object:
    for attr in ("structured_content", "data"):
        value = getattr(result, attr, None)
        if value is not None:
            return value
    content = getattr(result, "content", None)
    if content:
        texts = [getattr(c, "text", None) for c in content]
        return [t for t in texts if t is not None]
    return repr(result)


@router.post("/{name}/call", response_model=ToolCallResponse)
async def call_tool(name: str, payload: ToolCallRequest, request: Request) -> ToolCallResponse:
    runtime = request.app.state.runtime
    if runtime.mcp is None:
        raise HTTPException(status_code=503, detail="mcp not ready")
    try:
        result = await runtime.mcp.call_tool(name, payload.arguments)
    except Exception as exc:
        return ToolCallResponse(result=None, is_error=True, error=str(exc))
    return ToolCallResponse(result=_as_jsonable(result))
