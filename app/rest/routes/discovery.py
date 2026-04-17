"""GET /api/tools, GET /api/tools/{name}."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.rest.schemas import ToolSummary

router = APIRouter(prefix="/api/tools", tags=["discovery"])


@router.get("", response_model=list[ToolSummary])
async def list_tools(request: Request, tag: str | None = None) -> list[ToolSummary]:
    runtime = request.app.state.runtime
    if runtime.mcp is None:
        raise HTTPException(status_code=503, detail="mcp not ready")
    tools = await runtime.mcp.list_tools()
    out: list[ToolSummary] = []
    for t in tools:
        tags = sorted(getattr(t, "tags", set()) or set())
        if tag is not None and tag not in tags:
            continue
        out.append(
            ToolSummary(
                name=t.name,
                description=(t.description or "").strip() or None,
                tags=tags,
            )
        )
    return out


@router.get("/{name}", response_model=ToolSummary)
async def get_tool(name: str, request: Request) -> ToolSummary:
    runtime = request.app.state.runtime
    if runtime.mcp is None:
        raise HTTPException(status_code=503, detail="mcp not ready")
    try:
        tool = await runtime.mcp.get_tool(name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"tool not found: {name}") from exc
    return ToolSummary(
        name=tool.name,
        description=(tool.description or "").strip() or None,
        tags=sorted(getattr(tool, "tags", set()) or set()),
    )
