"""Structured MCP outputs for library search and candidate pool."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SearchLibraryResult(BaseModel):
    """Response from ``search_library``."""

    query: str
    total: int
    results: dict[str, list[dict[str, Any]]]


class CandidatePoolTrackRow(BaseModel):
    """Single track row in ``get_candidate_pool``."""

    id: int
    title: str
    bpm: float | None = None
    mood: str | None = None
    energy_lufs: float | None = None
    key_code: int | None = None


class GetCandidatePoolResult(BaseModel):
    """Response from ``get_candidate_pool``."""

    tracks: list[CandidatePoolTrackRow]
    total: int
    returned: int
    filters_applied: dict[str, Any]


SearchLibraryResult.model_rebuild()
CandidatePoolTrackRow.model_rebuild()
GetCandidatePoolResult.model_rebuild()
