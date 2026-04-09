"""Playlist DTOs shared by services and MCP tools."""

from __future__ import annotations

from pydantic import BaseModel


class PlaylistSummary(BaseModel):
    """Compact playlist projection for list views."""

    id: int
    name: str
    track_count: int = 0
    source_of_truth: str = "local"
