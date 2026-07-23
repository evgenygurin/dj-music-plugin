"""Apply a subgenre preset's overrides onto RenderSettings."""

from __future__ import annotations

from typing import Any

from app.config.render import RenderSettings
from app.domain.performance.subgenre_presets import resolve_preset
from app.handlers._context_log import safe_info


class SubgenrePresetApplier:
    async def apply(self, settings: RenderSettings, ctx: Any, subgenre: str | None) -> bool:
        if not subgenre:
            return False
        preset = resolve_preset(subgenre)
        if preset is None:
            return False
        preset.apply(settings)
        await safe_info(ctx, f"render_mixdown: subgenre preset {subgenre!r} applied")
        return True
