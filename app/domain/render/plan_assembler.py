"""Single render-plan assembly path for classic and prepared-stem modes."""

from __future__ import annotations

from typing import ClassVar, cast

from app.config.render import RenderSettings
from app.domain.render.bar_plan import BarPlan
from app.domain.render.models import (
    BeatgridEntry,
    RenderMode,
    RenderPlan,
    StemSegment,
    TrackInput,
    TrackSegment,
)
from app.domain.render.request import RenderRequest
from app.domain.render.segments import ClassicSegmentFactory, SegmentFactory, StemSegmentFactory
from app.domain.render.timeline import place_segments


class RenderPlanner:
    """Assemble a RenderPlan from a RenderRequest plus per-track geometry."""

    _FACTORIES: ClassVar[dict[RenderMode, SegmentFactory]] = {
        RenderMode.CLASSIC: ClassicSegmentFactory(),
        RenderMode.STEM: StemSegmentFactory(),
    }

    def __init__(self, settings: RenderSettings | None = None) -> None:
        self._settings = settings or RenderSettings()

    def assemble(
        self,
        settings: RenderSettings,
        request: RenderRequest,
        inputs: list[TrackInput],
        grid: dict[int, BeatgridEntry],
        bar_plan: BarPlan,
        stem_paths: dict[int, dict[str, str]] | None,
    ) -> RenderPlan:
        body_bars = request.body_bars or settings.body_bars
        transition_bars = request.transition_bars or settings.transition_bars
        per_transition_bars = list(bar_plan.transition_bars)
        per_body_bars = bar_plan.body_bars
        geometries = place_segments(
            inputs,
            grid,
            target_bpm=settings.target_bpm,
            body_bars=body_bars,
            transition_bars=transition_bars,
            per_transition_bars=per_transition_bars,
            per_body_bars=per_body_bars,
        )
        segments = self._FACTORIES[request.mode].build_segments(
            geometries,
            inputs,
            stem_paths,
            settings,
            request,
        )
        if request.mode is RenderMode.CLASSIC:
            return RenderPlan.from_settings(
                settings,
                request,
                segments=cast(list[TrackSegment], segments),
            )
        return RenderPlan.from_settings(
            settings,
            request,
            segments=[],
            stem_segments=cast(list[StemSegment], segments),
        )

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
        request = RenderRequest(
            version_id=0,
            workspace="",
            timestamp="",
            transition_bars=transition_bars,
            body_bars=body_bars,
            stem=False,
            filter_sweep=filter_sweep_preset,
            echo=echo_preset,
            crossfade_curve_out=crossfade_curve_out,
            crossfade_curve_in=crossfade_curve_in,
            reverb=reverb_preset,
            reverb_mix=reverb_mix,
        )
        bar_plan = BarPlan(
            transition_bars=tuple(per_transition_bars or ()),
            body_bars=list(per_body_bars or []),
        )
        return self.assemble(self._settings, request, inputs, grid, bar_plan, stem_paths=None)

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
        request = RenderRequest(
            version_id=0,
            workspace="",
            timestamp="",
            transition_bars=transition_bars,
            body_bars=body_bars,
            stem=True,
            filter_sweep=filter_sweep_preset,
            echo=echo_preset,
            crossfade_curve_out=crossfade_curve_out,
            crossfade_curve_in=crossfade_curve_in,
            reverb=reverb_preset,
            reverb_mix=reverb_mix,
        )
        bar_plan = BarPlan(
            transition_bars=tuple(per_transition_bars or ()),
            body_bars=list(per_body_bars or []),
        )
        return self.assemble(self._settings, request, inputs, grid, bar_plan, stem_paths_by_track)
