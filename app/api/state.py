"""Runtime state for the FastAPI wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

from fastapi import FastAPI, Request

from app.api.tool_registry import ToolRegistry
from app.providers.registry import ProviderRegistry


@dataclass
class ApiRuntimeState:
    """Mutable runtime state shared by API routes and lifespan hooks."""

    mcp: Any
    mcp_app: Any
    tool_registry: ToolRegistry
    ym_client: Any | None = None
    provider_registry: ProviderRegistry = field(default_factory=ProviderRegistry)
    mcp_ready: bool = False


def build_api_runtime(mcp: Any) -> ApiRuntimeState:
    """Construct the runtime state for the FastAPI wrapper."""
    return ApiRuntimeState(
        mcp=mcp,
        mcp_app=mcp.http_app(path="/"),
        tool_registry=ToolRegistry.discover(),
    )


def get_runtime(source: Request | FastAPI) -> ApiRuntimeState:
    """Return the typed API runtime state from a request or app object."""
    app = source.app if isinstance(source, Request) else source
    return cast(ApiRuntimeState, app.state.runtime)
