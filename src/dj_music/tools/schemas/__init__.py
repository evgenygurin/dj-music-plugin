"""Pydantic schemas specific to the MCP presentation layer.

Only models that exist *solely* to shape MCP tool output live here. Shared
domain DTOs (``TrackBrief``, ``PlaylistSummary`` etc.) live in
:mod:`app.schemas` because services consume them as return types.

Currently exposes:
- ``SearchQuery``, ``SimilarTrackSearchStrategy`` — LLM sampling structured output
"""

from __future__ import annotations

from dj_music.tools.schemas.sampling import SearchQuery, SimilarTrackSearchStrategy

__all__ = [
    "SearchQuery",
    "SimilarTrackSearchStrategy",
]
