from __future__ import annotations

from app.config.render import RenderSettings
from app.domain.render.models import BeatgridEntry, RenderPlan, TrackInput
from app.domain.render.timeline import build_render_plan, build_stem_render_plan


class RenderPlanBuilder:
    def __init__(self, settings: RenderSettings) -> None:
        self._settings = settings

    def build_classic(
        self,
        inputs: list[TrackInput],
        grid: dict[int, BeatgridEntry],
        *,
        body_bars: int,
        transition_bars: int,
        per_transition_bars: list[int] | None = None,
        per_body_bars: list[int] | None = None,
        filter_sweep_preset: str | None = None,
        echo_preset: str | None = None,
        crossfade_curve_out: str = "tri",
        crossfade_curve_in: str = "exp",
        reverb_preset: str | None = None,
        reverb_mix: float = 0.25,
    ) -> RenderPlan:
        rs = self._settings
        return build_render_plan(
            inputs,
            grid,
            target_bpm=rs.target_bpm,
            body_bars=body_bars,
            transition_bars=transition_bars,
            xsplit_low_hz=rs.xsplit_low_hz,
            xsplit_high_hz=rs.xsplit_high_hz,
            eq_phase_1_ratio=rs.eq_phase_1_ratio,
            eq_phase_2_ratio=rs.eq_phase_2_ratio,
            low_swap_beats=rs.low_swap_beats,
            outro_fade_bars=rs.outro_fade_bars,
            limiter_ceiling=rs.limiter_ceiling,
            per_transition_bars=per_transition_bars,
            per_body_bars=per_body_bars,
            filter_sweep_preset=filter_sweep_preset,
            echo_preset=echo_preset,
            crossfade_curve_out=crossfade_curve_out,
            crossfade_curve_in=crossfade_curve_in,
            reverb_preset=reverb_preset,
            reverb_mix=reverb_mix,
        )

    def build_stem(
        self,
        inputs: list[TrackInput],
        stem_paths_by_track: dict[int, dict[str, str]],
        grid: dict[int, BeatgridEntry],
        *,
        body_bars: int,
        transition_bars: int,
        per_transition_bars: list[int] | None = None,
        per_body_bars: list[int] | None = None,
        filter_sweep_preset: str | None = None,
        echo_preset: str | None = None,
        crossfade_curve_out: str = "tri",
        crossfade_curve_in: str = "exp",
        reverb_preset: str | None = None,
        reverb_mix: float = 0.25,
    ) -> RenderPlan:
        rs = self._settings
        return build_stem_render_plan(
            inputs,
            stem_paths_by_track,
            grid,
            target_bpm=rs.target_bpm,
            body_bars=body_bars,
            transition_bars=transition_bars,
            xsplit_low_hz=rs.xsplit_low_hz,
            xsplit_high_hz=rs.xsplit_high_hz,
            eq_phase_1_ratio=rs.eq_phase_1_ratio,
            eq_phase_2_ratio=rs.eq_phase_2_ratio,
            low_swap_beats=rs.low_swap_beats,
            outro_fade_bars=rs.outro_fade_bars,
            limiter_ceiling=rs.limiter_ceiling,
            per_transition_bars=per_transition_bars,
            per_body_bars=per_body_bars,
            filter_sweep_preset=filter_sweep_preset,
            echo_preset=echo_preset,
            crossfade_curve_out=crossfade_curve_out,
            crossfade_curve_in=crossfade_curve_in,
            reverb_preset=reverb_preset,
            reverb_mix=reverb_mix,
        )
