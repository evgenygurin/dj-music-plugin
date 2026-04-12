"""Yandex Music response DTOs shared by services and MCP tools."""

from __future__ import annotations

from pydantic import BaseModel


class YMTrackSummary(BaseModel):
    """Compact YM track info for tool output."""

    ym_id: str
    title: str
    artists: str
    duration_ms: int | None = None
    album_id: str = ""
    album_genre: str = ""
