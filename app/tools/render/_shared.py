"""Workspace-path + clock helpers for the render tools.

The tools inject the timestamp (clock) so the pure/domain layers never call
Date.now — keeps everything deterministic and testable.
"""

from __future__ import annotations

from app.shared.time import utc_now
from app.shared.workspace import render_workspace

__all__ = ["render_timestamp", "render_workspace"]


def render_timestamp() -> str:
    """Sortable job timestamp, e.g. 20260706-142530."""
    return utc_now().strftime("%Y%m%d-%H%M%S")
