"""ui_library_dashboard — Prefab global library dashboard.

Summary row (total tracks, analyzed, coverage) + BarChart (BPM histogram) +
PieChart (mood distribution) + BarChart (Camelot distribution).

Uses ``entity_aggregate``-style queries via ``BaseRepository.aggregate`` and
``filter`` on ``track_features`` — same primitives the existing CRUD tools
already rely on.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.domain.camelot.wheel import key_code_to_camelot
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.ui_colors import CAMELOT_WHEEL_COLORS, SUBGENRE_COLORS
from app.tools.ui._fallback import DashboardFallback, fallback_or, supports_ui

try:
    from prefab_ui.components import (
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
    from prefab_ui.components.charts import BarChart, ChartSeries, PieChart
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "ui_library_dashboard requires prefab-ui. Install with: uv sync --all-extras "
        "(or `pip install 'fastmcp[apps]'`)."
    ) from _exc

_BPM_BUCKETS: list[tuple[str, float, float]] = [
    ("<110", 0.0, 110.0),
    ("110-119", 110.0, 120.0),
    ("120-124", 120.0, 125.0),
    ("125-129", 125.0, 130.0),
    ("130-134", 130.0, 135.0),
    ("135-139", 135.0, 140.0),
    ("140-149", 140.0, 150.0),
    (">=150", 150.0, 1e9),
]


async def _gather(uow: UnitOfWork) -> dict[str, Any]:
    total = await uow.tracks.count()
    analyzed = await uow.track_features.count()

    # Pull every analyzed feature row. Audit (iter 1) caught the prior
    # ``.limit(10000)`` silently dropping ~60% of the production
    # library. Three tiny columns over 24k rows is ~700 KB - no need
    # for the cap; the dashboard is on-demand, not realtime.
    session = uow.track_features.session
    from sqlalchemy import select

    stmt = select(
        TrackAudioFeaturesComputed.bpm,
        TrackAudioFeaturesComputed.key_code,
        TrackAudioFeaturesComputed.mood,
    )
    rows = (await session.execute(stmt)).all()

    bpm_hist: Counter[str] = Counter()
    mood_hist: Counter[str] = Counter()
    camelot_hist: Counter[str] = Counter()
    for bpm, key_code, mood in rows:
        if bpm is not None:
            for label, lo, hi in _BPM_BUCKETS:
                if lo <= float(bpm) < hi:
                    bpm_hist[label] += 1
                    break
        if key_code is not None:
            try:
                camelot_hist[key_code_to_camelot(int(key_code))] += 1
            except ValueError:
                continue
        if mood:
            mood_hist[mood] += 1

    coverage = (analyzed / total) if total else 0.0
    # Emit ``bpm_histogram`` in ascending bucket order — Counter's
    # insertion order is whatever bucket appeared first in the data,
    # which scrambles the chart on Prefab-blind clients consuming the
    # JSON fallback (audit iter 1).
    bpm_histogram_ordered = {label: bpm_hist.get(label, 0) for label, _, _ in _BPM_BUCKETS}
    return {
        "total_tracks": total,
        "analyzed_tracks": analyzed,
        "coverage": coverage,
        "bpm_histogram": bpm_histogram_ordered,
        "mood_distribution": dict(mood_hist),
        "camelot_distribution": dict(camelot_hist),
    }


@tool(
    name="ui_library_dashboard",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    description=(
        "Prefab global library dashboard: totals + BPM histogram + mood PieChart "
        "+ Camelot BarChart. Fallback: JSON payload."
    ),
    timeout=30.0,
)
async def ui_library_dashboard(
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Column | DashboardFallback:
    data = await _gather(uow)

    if not supports_ui(ctx):
        return fallback_or(DashboardFallback, data)

    bpm_rows = [
        {"bucket": label, "count": data["bpm_histogram"].get(label, 0)}
        for label, _lo, _hi in _BPM_BUCKETS
    ]
    mood_rows = [
        {
            "mood": name,
            "count": count,
            "color": SUBGENRE_COLORS.get(name, "#64748b"),
        }
        for name, count in sorted(data["mood_distribution"].items(), key=lambda kv: -kv[1])
    ]
    camelot_rows = [
        {
            "camelot": name,
            "count": count,
            "color": CAMELOT_WHEEL_COLORS.get(name, "#64748b"),
        }
        for name, count in sorted(
            data["camelot_distribution"].items(),
            key=lambda kv: (kv[0][-1], int(kv[0][:-1])),
        )
    ]

    with Column(gap=4, css_class="p-6") as view:
        Heading("Library Dashboard")
        with Row(gap=4):
            Metric(label="Total tracks", value=str(data["total_tracks"]))
            Metric(label="Analyzed", value=str(data["analyzed_tracks"]))
            Metric(
                label="Coverage",
                value=f"{data['coverage'] * 100:.0f}%",
                trend_sentiment=("positive" if data["coverage"] >= 0.9 else "neutral"),
            )
        with Card():
            CardHeader(children=[CardTitle("BPM distribution")])
            CardContent(
                children=[
                    BarChart(
                        data=bpm_rows,
                        series=[ChartSeries(data_key="count", label="Tracks", color="#34d399")],
                        x_axis="bucket",
                        show_grid=True,
                        show_legend=False,
                        height=220,
                    ),
                ]
            )
        with Row(gap=4):
            with Card():
                CardHeader(children=[CardTitle("Moods")])
                CardContent(
                    children=[
                        PieChart(
                            data=mood_rows,
                            data_key="count",
                            name_key="mood",
                            show_label=True,
                            show_legend=True,
                            height=260,
                        )
                        if mood_rows
                        else Muted("No mood data."),
                    ]
                )
            with Card():
                CardHeader(children=[CardTitle("Camelot wheel")])
                CardContent(
                    children=[
                        BarChart(
                            data=camelot_rows,
                            series=[ChartSeries(data_key="count", label="Tracks")],
                            x_axis="camelot",
                            show_grid=True,
                            show_legend=False,
                            height=260,
                        )
                        if camelot_rows
                        else Muted("No key data."),
                    ]
                )
    return view
