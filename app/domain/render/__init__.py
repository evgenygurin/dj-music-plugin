"""Pure render-plan compute (no IO). See docs/render-pipeline.md."""

from app.domain.render.bar_planner import BarPlanner
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
from app.domain.render.plan_builder import RenderPlanBuilder
from app.domain.render.stem_graph import build_stem_filtergraph
from app.domain.render.timeline import (
    SegmentGeometry,
    TimelineWindows,
    TransitionWindow,
    build_render_plan,
    build_stem_render_plan,
    place_segments,
    timeline_windows,
)

__all__ = [
    "STEM_ORDER",
    "BarPlanner",
    "BeatgridEntry",
    "RenderMode",
    "RenderPlan",
    "RenderPlanBuilder",
    "RenderStrategy",
    "SegmentGeometry",
    "StemSegment",
    "TimelineWindows",
    "TrackInput",
    "TrackSegment",
    "TransitionWindow",
    "build_filtergraph",
    "build_render_plan",
    "build_stem_filtergraph",
    "build_stem_render_plan",
    "gains_to_median",
    "place_segments",
    "select_strategy",
    "timeline_windows",
]
