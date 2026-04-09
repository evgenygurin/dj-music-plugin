"""DJ set DTOs shared by services and MCP tools."""

from __future__ import annotations

from pydantic import BaseModel


class SetSummary(BaseModel):
    """Compact DJ set projection for list views."""

    id: int
    name: str
    track_count: int = 0
    template: str | None = None
    latest_score: float | None = None
