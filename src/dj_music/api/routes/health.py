"""Health and operational endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from dj_music.api.state import get_runtime

router = APIRouter()


@router.get(
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
def health(request: Request) -> dict[str, str | int | bool]:
    """Проверка работоспособности сервера."""
    runtime = get_runtime(request)
    return {
        "status": "ok",
        "tools_discovered": len(runtime.tool_registry.tools),
        "mcp_ready": runtime.mcp_ready,
    }
