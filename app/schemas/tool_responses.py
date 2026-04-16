"""Backward-compatible re-exports for MCP structured output models.

Implementation lives in :mod:`app.schemas.tool_output`.
"""

from __future__ import annotations

from app.schemas.tool_output import (
    CandidatePoolTrackRow,
    GetCandidatePoolResult,
    GetSetCheatSheetResult,
    GetSetTemplatesResult,
    ListSetsResult,
    SearchLibraryResult,
    SearchTransitionsResult,
    SetArcPreview,
    SetTemplateEntry,
    SetTemplateSlotRow,
    SetVersionResult,
    TransitionScoreResult,
)

__all__ = [
    "CandidatePoolTrackRow",
    "GetCandidatePoolResult",
    "GetSetCheatSheetResult",
    "GetSetTemplatesResult",
    "ListSetsResult",
    "SearchLibraryResult",
    "SearchTransitionsResult",
    "SetArcPreview",
    "SetTemplateEntry",
    "SetTemplateSlotRow",
    "SetVersionResult",
    "TransitionScoreResult",
]
