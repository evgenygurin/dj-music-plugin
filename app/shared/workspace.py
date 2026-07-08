"""Shared workspace-path helpers."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings


def render_workspace(version_id: int) -> str:
    """`<DeliverySettings.output_dir>/<RenderSettings.workspace_subdir>/v{id}`."""
    s = get_settings()
    root = Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"
    return str(root)
