"""RenderRequest — Parameter Object bundling all per-render knobs.

Replaces the 14-kwarg pass-through chain tool → handler → builder → timeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.domain.render.models import RenderMode


@dataclass(frozen=True, slots=True)
class RenderRequest:
    version_id: int
    workspace: str
    timestamp: str
    out_name: str | None = None
    transition_bars: int | None = None
    body_bars: int | None = None
    refresh_grid: bool = False
    stem: bool = True
    subgenre: str | None = None
    filter_sweep: str | None = None
    echo: str | None = None
    crossfade_curve_out: str = "tri"
    crossfade_curve_in: str = "exp"
    reverb: str | None = None
    reverb_mix: float = 0.25

    @property
    def mode(self) -> RenderMode:
        return RenderMode.STEM if self.stem else RenderMode.CLASSIC

    @property
    def out_filename(self) -> str:
        return self.out_name or get_settings().render.mix_filename
