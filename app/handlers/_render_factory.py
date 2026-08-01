"""Shared factory for building RenderRequest — eliminates parameter duplication
between ``render_mixdown_handler`` and ``render_mixdown_extended_handler``.
"""

from __future__ import annotations

from typing import Any

from app.domain.render.request import RenderRequest


def build_render_request(
    *,
    version_id: int,
    workspace: str,
    timestamp: str,
    out_name: str | None = None,
    transition_bars: int | None = None,
    body_bars: int | None = None,
    refresh_grid: bool = False,
    stem: bool = True,
    subgenre: str | None = None,
    filter_sweep: str | None = None,
    echo: str | None = None,
    crossfade_curve_out: str = "tri",
    crossfade_curve_in: str = "exp",
    reverb: str | None = None,
    reverb_mix: float = 0.25,
    **_kwargs: Any,
) -> RenderRequest:
    return RenderRequest(
        version_id=version_id,
        workspace=workspace,
        timestamp=timestamp,
        out_name=out_name,
        transition_bars=transition_bars,
        body_bars=body_bars,
        refresh_grid=refresh_grid,
        stem=stem,
        subgenre=subgenre,
        filter_sweep=filter_sweep,
        echo=echo,
        crossfade_curve_out=crossfade_curve_out,
        crossfade_curve_in=crossfade_curve_in,
        reverb=reverb,
        reverb_mix=reverb_mix,
    )
