"""ui_transition_score — Prefab breakdown of a stem-aware transition score.

Renders a RadarChart of the six scoring components + a Card with
hard-constraint status + a Card with the picked Neural Mix preset.
Reuses ``TransitionScorer`` via DI; the picked preset is the
``best_transition`` argmax exposed by the scorer (post Neural Mix
refactor).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_transition_scorer, get_uow
from app.shared.errors import NotFoundError
from app.tools.ui._fallback import (
    TransitionScoreFallback,
    fallback_or,
    supports_ui,
)

try:
    from prefab_ui.components import (
        Badge,
        Card,
        CardContent,
        CardHeader,
        CardTitle,
        Column,
        Heading,
        Metric,
        Muted,
        Row,
    )
    from prefab_ui.components.charts import RadarChart
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "ui_transition_score requires prefab-ui. Install with: uv sync --all-extras "
        "(or `pip install 'fastmcp[apps]'`)."
    ) from _exc

# UI label → ``TransitionScore`` attribute. The dataclass moved to
# stem-named fields (``harmonics`` / ``bass`` / ``drums`` / ``vocals``)
# but ``docs/transition-scoring.md`` still presents them as the v0
# conceptual labels (``harmonic`` / ``spectral`` / ``groove`` /
# ``timbral``) — the radar chart keeps the v0 labels for axis text
# while reading the actual attribute via this map. Smoke test
# 2026-05-07: prior tuple did ``getattr(score, "harmonic", 0.0)``
# blind, which silently returned ``0.0`` for four of the six axes
# because no such attribute exists on the dataclass.
_COMPONENT_FIELD_MAP: dict[str, str] = {
    "bpm": "bpm",
    "harmonic": "harmonics",
    "energy": "energy",
    "spectral": "bass",
    "groove": "drums",
    "timbral": "vocals",
}
_COMPONENTS = tuple(_COMPONENT_FIELD_MAP)


def _parse_intent(value: str | None) -> TransitionIntent | None:
    if value is None:
        return None
    try:
        return TransitionIntent(value)
    except ValueError as err:
        msg = f"unknown intent {value!r}; allowed: {[i.value for i in TransitionIntent]}"
        raise ValueError(msg) from err


async def _compute(
    uow: UnitOfWork, scorer: Any, a: int, b: int, intent: str | None
) -> dict[str, Any]:
    # Mixing a track into itself is meaningless and elsewhere in the v1
    # surface (``transition_score_pool``, ``entity_create(transition)``,
    # ``sequence_optimize``) it is rejected up front. Mirror that here so
    # ``ui_transition_score(from=1, to=1)`` does not silently return a
    # bogus 0.9 overall (synthetic self-similarity numbers).
    if a == b:
        raise ValueError(f"from_track_id and to_track_id must differ; got {a} for both")
    feats = await uow.track_features.get_scoring_features_batch([a, b])
    if a not in feats:
        raise NotFoundError("track_features", a)
    if b not in feats:
        raise NotFoundError("track_features", b)
    score = scorer.score(feats[a], feats[b], intent=_parse_intent(intent))
    transition = score.best_transition.value if score.best_transition is not None else None
    return {
        "from_track_id": a,
        "to_track_id": b,
        "components": {
            label: float(getattr(score, attr, 0.0) or 0.0)
            for label, attr in _COMPONENT_FIELD_MAP.items()
        },
        "overall": float(score.overall or 0.0),
        "hard_reject": bool(score.hard_reject),
        "reject_reason": score.reject_reason,
        "style": transition,
        "style_bars": DEFAULT_TRANSITION_BARS,
        "style_reason": (
            f"Neural Mix preset selected by stem-aware argmax over {len(_COMPONENTS)} components"
            if transition is not None
            else None
        ),
    }


@tool(
    name="ui_transition_score",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    description=(
        "Prefab breakdown of the stem-aware transition score between two tracks: "
        "RadarChart, hard-constraint status, picked Neural Mix preset. Fallback: JSON payload."
    ),
    timeout=30.0,
)
async def ui_transition_score(
    from_track_id: Annotated[int, Field(description="Outgoing track ID")],
    to_track_id: Annotated[int, Field(description="Incoming track ID")],
    intent: Annotated[
        str | None, Field(description="Optional transition intent (e.g. 'build', 'close')")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> Column | TransitionScoreFallback:
    data = await _compute(uow, scorer, from_track_id, to_track_id, intent)

    if not supports_ui(ctx):
        return fallback_or(TransitionScoreFallback, data)

    radar_data = [
        {"axis": c.upper(), "score": round(data["components"][c], 3)} for c in _COMPONENTS
    ]

    with Column(gap=4, css_class="p-6") as view:
        Heading(f"Transition {from_track_id} → {to_track_id}")
        Muted(
            f"intent={intent or 'auto'}  ·  overall={data['overall']:.2f}"
            + (f"  ·  ✗ {data['reject_reason']}" if data["hard_reject"] else "")
        )
        with Row(gap=4):
            Metric(
                label="Overall",
                value=f"{data['overall']:.2f}",
                trend_sentiment="positive" if data["overall"] >= 0.6 else "negative",
            )
            Metric(label="Preset", value=str(data["style"] or "—"))
            Metric(label="Bars", value=str(data["style_bars"]))
        RadarChart(
            data=radar_data,
            series=[
                {"data_key": "score", "label": "Score", "color": "#34d399"},
            ],
            axis_key="axis",
            filled=True,
            show_legend=False,
            show_grid=True,
            height=320,
        )
        with Card():
            CardHeader(children=[CardTitle("Hard Constraints")])
            CardContent(
                children=[
                    Badge(
                        label="REJECT" if data["hard_reject"] else "PASS",
                        variant="destructive" if data["hard_reject"] else "default",
                    ),
                    Muted(data["reject_reason"] or "all thresholds within limits"),
                ]
            )
        with Card():
            CardHeader(children=[CardTitle(f"Preset: {data['style'] or '—'}")])
            CardContent(
                children=[
                    Muted(
                        f"{data['style_bars']} bars  ·  "
                        f"{data['style_reason'] or 'no preset (hard reject)'}"
                    ),
                ]
            )
    return view
