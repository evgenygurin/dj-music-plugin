"""Pydantic DTOs for REST endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    mcp_ready: bool
    tool_count: int
    degraded_reason: str | None = None


class ToolSummary(BaseModel):
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class ToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    result: Any = None
    is_error: bool = False
    error: str | None = None
