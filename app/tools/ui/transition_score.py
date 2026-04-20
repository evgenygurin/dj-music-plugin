"""ui_transition_score — Prefab breakdown of a 6-component transition score.

Renders a RadarChart of the 6 scoring components + a Card with hard-constraint
status + a Card with recommended style + recipe. Reuses ``TransitionScorer``
via DI and ``recommend_style`` from the pure domain module.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.style import recommend_style, style_profile
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_transition_scorer, get_uow
from app.shared.errors import NotFoundError
from app.tools.ui._fallback import (
    TransitionScoreFallback,
    fallback_or,
    supports_ui,
)
from app.tools.ui._prefab import (
    Badge,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Column,
    Heading,
    Metric,
    Muted,
    RadarChart,
    Row,
)

_COMPONENTS = ("bpm", "harmonic", "energy", "spectral", "groove", "timbral")


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
    feats = await uow.track_features.get_scoring_features_batch([a, b])
    if a not in feats:
        raise NotFoundError("track_features", a)
    if b not in feats:
        raise NotFoundError("track_features", b)
    score = scorer.score(feats[a], feats[b], intent=_parse_intent(intent))
    style = recommend_style(score)
    profile = style_profile(style)
    return {
        "from_track_id": a,
        "to_track_id": b,
        "components": {c: float(getattr(score, c, 0.0) or 0.0) for c in _COMPONENTS},
        "overall": float(score.overall or 0.0),
        "hard_reject": bool(score.hard_reject),
        "reject_reason": score.reject_reason,
        "style": style.value,
        "style_bars": int(profile.get("bars", 0) or 0),
        "style_reason": profile.get("reason"),
    }


@tool(
    name="ui_transition_score",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    description=(
        "Prefab breakdown of the 6-component transition score between two tracks: "
        "RadarChart, hard-constraint status, style recipe. Fallback: JSON payload."
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
            Metric(label="Style", value=str(data["style"]))
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
            CardHeader(children=[CardTitle(f"Style: {data['style']}")])
            CardContent(
                children=[
                    Muted(
                        f"{data['style_bars']} bars  ·  "
                        f"{data['style_reason'] or 'no reason provided'}"
                    ),
                ]
            )
    return view
