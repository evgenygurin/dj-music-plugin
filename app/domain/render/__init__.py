"""Pure render-plan compute (no IO). See docs/render-pipeline.md."""

from app.domain.render.bar_plan import BarPlan, BarPlanner
from app.domain.render.beatgrid import (
    BeatgridIO,
    BeatgridLimits,
    clamp_entry,
    entry_flags,
    entry_from_row,
    entry_to_row,
)
from app.domain.render.effects_resolver import EffectPresetResolver, ResolvedEffects
from app.domain.render.filtergraph import RenderStrategy, select_strategy
from app.domain.render.graph import build_filtergraph
from app.domain.render.levels import gains_to_median
from app.domain.render.models import (
    STEM_ORDER,
    BeatgridEntry,
    RenderMode,
    RenderPlan,
    StemSegment,
    TrackInput,
    TrackSegment,
)
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest
from app.domain.render.segments import ClassicSegmentFactory, SegmentFactory, StemSegmentFactory
from app.domain.render.stem_graph import build_stem_filtergraph
from app.domain.render.stem_voicing import STEM_VOICING, StemVoicing
from app.domain.render.timeline import (
    SegmentGeometry,
    TimelineWindows,
    TransitionWindow,
    place_segments,
    timeline_windows,
)

__all__ = [
    "STEM_ORDER",
    "STEM_VOICING",
    "BarPlan",
    "BarPlanner",
    "BeatgridEntry",
    "BeatgridIO",
    "BeatgridLimits",
    "ClassicSegmentFactory",
    "EffectPresetResolver",
    "RenderMode",
    "RenderPlan",
    "RenderPlanner",
    "RenderRequest",
    "RenderStrategy",
    "ResolvedEffects",
    "SegmentFactory",
    "SegmentGeometry",
    "StemSegment",
    "StemSegmentFactory",
    "StemVoicing",
    "TimelineWindows",
    "TrackInput",
    "TrackSegment",
    "TransitionWindow",
    "build_filtergraph",
    "build_stem_filtergraph",
    "clamp_entry",
    "entry_flags",
    "entry_from_row",
    "entry_to_row",
    "gains_to_median",
    "place_segments",
    "select_strategy",
    "timeline_windows",
]
