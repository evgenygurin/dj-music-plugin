"""Track DTOs shared by services and MCP tools."""

from __future__ import annotations

from pydantic import BaseModel


class TrackBrief(BaseModel):
    """Minimal track projection for list views."""

    id: int
    title: str
    artist_names: list[str]
    bpm: float | None = None
    key_camelot: str | None = None
    duration_ms: int | None = None


class TrackStandard(TrackBrief):
    """Standard track projection — brief plus mood/energy summary."""

    energy_lufs: float | None = None
    mood: str | None = None
    status: int = 0
    has_features: bool = False
