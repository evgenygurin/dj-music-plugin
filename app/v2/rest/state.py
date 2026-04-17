"""Shared runtime state for the REST wrapper."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApiRuntimeState:
    mcp_ready: bool = False
    mcp: Any | None = None
    degraded_reason: str | None = None
    tool_cache: dict[str, Any] = field(default_factory=dict)
