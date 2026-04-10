"""Runtime state for the FastAPI wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from fastapi import FastAPI, Request

from app.api.services.signed_url_cache import SignedUrlCache
from app.api.services.tool_registry import ToolRegistry
from app.api.services.ym_audio_proxy import YmAudioProxy


@dataclass
class ApiRuntimeState:
    """Mutable runtime state shared by API routes and lifespan hooks."""

    mcp: Any
    mcp_app: Any
    tool_registry: ToolRegistry
    signed_url_cache: SignedUrlCache
    ym_audio_proxy: YmAudioProxy
    ym_client: Any | None = None
    mcp_ready: bool = False


def build_api_runtime(mcp: Any) -> ApiRuntimeState:
    """Construct the runtime state for the FastAPI wrapper."""
    signed_url_cache = SignedUrlCache()
    runtime = ApiRuntimeState(
        mcp=mcp,
        mcp_app=mcp.http_app(path="/"),
        tool_registry=ToolRegistry.discover(),
        signed_url_cache=signed_url_cache,
        ym_audio_proxy=None,  # type: ignore[arg-type]
    )
    runtime.ym_audio_proxy = YmAudioProxy(
        signed_url_cache=signed_url_cache,
        get_ym_client=lambda: runtime.ym_client,
    )
    return runtime


def get_runtime(source: Request | FastAPI) -> ApiRuntimeState:
    """Return the typed API runtime state from a request or app object."""
    app = source.app if isinstance(source, Request) else source
    return cast(ApiRuntimeState, app.state.runtime)
