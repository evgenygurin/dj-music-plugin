"""Workspace-path + clock helpers for the render tools.

The tools inject the timestamp (clock) so the pure/domain layers never call
Date.now — keeps everything deterministic and testable.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.shared.time import utc_now


def render_workspace(version_id: int) -> str:
    """`<DeliverySettings.output_dir>/<RenderSettings.workspace_subdir>/v{id}`."""
    s = get_settings()
    root = Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"
    return str(root)


def render_timestamp() -> str:
    """Sortable job timestamp, e.g. 20260706-142530."""
    return utc_now().strftime("%Y%m%d-%H%M%S")
