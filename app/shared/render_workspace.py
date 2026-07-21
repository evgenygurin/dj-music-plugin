from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.shared.time import utc_now


def render_workspace(version_id: int) -> str:
    s = get_settings()
    root = Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"
    return str(root)


def render_mix_path(version_id: int, name: str | None = None) -> str:
    filename = name or get_settings().render.mix_filename
    return str(Path(render_workspace(version_id)) / filename)


def render_timestamp() -> str:
    return utc_now().strftime("%Y%m%d-%H%M%S")
