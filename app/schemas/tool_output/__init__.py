"""Pydantic models for MCP tool structured output (FastMCP ``output_schema``).

Prefer importing from this package; :mod:`app.schemas.tool_responses` re-exports the same names.
"""

from __future__ import annotations

from app.schemas.tool_output.dj_set_tools import (
    GetSetCheatSheetResult,
    GetSetTemplatesResult,
    ListSetsResult,
    SetArcPreview,
    SetTemplateEntry,
    SetTemplateSlotRow,
    SetVersionResult,
    TransitionScoreResult,
)
from app.schemas.tool_output.library_tools import (
    CandidatePoolTrackRow,
    GetCandidatePoolResult,
    SearchLibraryResult,
)

__all__ = [
    "CandidatePoolTrackRow",
    "GetCandidatePoolResult",
    "GetSetCheatSheetResult",
    "GetSetTemplatesResult",
    "ListSetsResult",
    "SearchLibraryResult",
    "SetArcPreview",
    "SetTemplateEntry",
    "SetTemplateSlotRow",
    "SetVersionResult",
    "TransitionScoreResult",
]
