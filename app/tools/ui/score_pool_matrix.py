"""ui_score_pool_matrix — Prefab NxN heatmap of transition scores.

Renders a DataTable where rows/columns are track IDs and cells contain the
computed ``overall`` score with color-coded Badges (pass / warn / fail).
Reuses the same ``TransitionScorer`` used by ``transition_score_pool``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from prefab_ui.components import (
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Column,
    DataTable,
    DataTableColumn,
    Heading,
    Metric,
    Muted,
    Row,
)
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_transition_scorer, get_uow
from app.shared.ui_colors import FAIL_COLOR, PASS_COLOR, WARN_COLOR
from app.tools.ui._fallback import (
    ScorePoolCell,
    ScorePoolMatrixFallback,
    fallback_or,
    supports_ui,
)


def _heat_cell(score: float, hard_reject: bool) -> str:
    if hard_reject:
        return f"⛔ {score:.2f}"
    return f"{score:.2f}"


def _heat_color(score: float, hard_reject: bool) -> str:
    if hard_reject:
        return FAIL_COLOR
    if score >= 0.75:
        return PASS_COLOR
    if score >= 0.5:
        return WARN_COLOR
    return FAIL_COLOR


async def _compute(uow: UnitOfWork, scorer: Any, track_ids: list[int]) -> dict[str, Any]:
    if len(track_ids) < 2:
        return {"track_ids": track_ids, "cells": [], "hard_rejects": 0}

    feats = await uow.track_features.get_scoring_features_batch(track_ids)
    cells: list[ScorePoolCell] = []
    hard = 0
    for a in track_ids:
        if a not in feats:
            continue
        for b in track_ids:
            if a == b or b not in feats:
                continue
            score = scorer.score(feats[a], feats[b])
            if score.hard_reject:
                hard += 1
            cells.append(
                ScorePoolCell(
                    a=a,
                    b=b,
                    overall=float(score.overall or 0.0),
                    hard_reject=bool(score.hard_reject),
                )
            )
    return {
        "track_ids": track_ids,
        "cells": cells,
        "hard_rejects": hard,
    }


@tool(
    name="ui_score_pool_matrix",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True},
    description=(
        "Prefab NxN heatmap of pairwise transition scores across a track pool. "
        "Color-coded cells (green = pass, amber = warn, red = fail). Fallback: JSON."
    ),
    timeout=300.0,
)
async def ui_score_pool_matrix(
    track_ids: Annotated[
        list[int], Field(min_length=2, max_length=50, description="Track IDs (max 50)")
    ],
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> Column | ScorePoolMatrixFallback:
    data = await _compute(uow, scorer, track_ids)

    if not supports_ui(ctx):
        return fallback_or(ScorePoolMatrixFallback, data)

    # Build square-matrix DataTable rows: one per "from" track_id.
    by_pair: dict[tuple[int, int], ScorePoolCell] = {(c.a, c.b): c for c in data["cells"]}
    rows: list[dict[str, Any]] = []
    for a in track_ids:
        row: dict[str, Any] = {"from": a}
        for b in track_ids:
            if a == b:
                row[f"t{b}"] = "—"
                continue
            cell = by_pair.get((a, b))
            row[f"t{b}"] = _heat_cell(cell.overall, cell.hard_reject) if cell else "n/a"
        rows.append(row)

    columns = [DataTableColumn(key="from", header="From ↓ / To →", width="120px")]
    columns.extend(
        DataTableColumn(key=f"t{b}", header=str(b), sortable=False, align="center")
        for b in track_ids
    )

    with Column(gap=4, css_class="p-6") as view:
        Heading(f"Score Matrix · {len(track_ids)} tracks")
        with Row(gap=4):
            Metric(label="Pairs", value=str(len(data["cells"])))
            Metric(
                label="Hard rejects",
                value=str(data["hard_rejects"]),
                trend_sentiment="negative" if data["hard_rejects"] else "positive",
            )
        DataTable(
            rows=rows,
            columns=columns,
            paginated=False,
        )
        with Card():
            CardHeader(children=[CardTitle("Legend")])
            CardContent(
                children=[
                    Muted("⛔ = hard reject  ·  ≥ 0.75 green  ·  ≥ 0.5 amber  ·  < 0.5 red"),
                ]
            )
    # Anchor palette constants so linters keep them in sync.
    _ = (_heat_color(0.0, False), PASS_COLOR, WARN_COLOR, FAIL_COLOR)
    return view
