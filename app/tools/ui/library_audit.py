"""ui_library_audit — Prefab audit view for a playlist (or the full library).

Summary Card row (total, pass, fail, coverage) + PieChart of subgenre
distribution + DataTable with pass/fail Badges per track. Reuses the
``run_audit_rules`` pure-domain function and the same feature batch loader
used by ``local://playlists/{id}/audit``.
"""

from __future__ import annotations

from collections import Counter
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
from prefab_ui.components.charts import PieChart
from pydantic import Field

from app.domain.audit.rules import DEFAULT_AUDIT_RULES, run_audit_rules
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.shared.ui_colors import SUBGENRE_COLORS
from app.tools.ui._fallback import (
    AuditTrackRow,
    LibraryAuditFallback,
    fallback_or,
    supports_ui,
)


async def _gather(uow: UnitOfWork, playlist_id: int | None) -> dict[str, Any]:
    if playlist_id is not None:
        if await uow.playlists.get(playlist_id) is None:
            raise NotFoundError("playlist", playlist_id)
        track_ids = await uow.playlists.get_track_ids(playlist_id)
    else:
        page = await uow.tracks.filter(limit=500)
        track_ids = [r.id for r in page.items]

    feat_map = await uow.track_features.get_scoring_features_batch(track_ids)
    track_map = await uow.tracks.get_many(track_ids)

    per_track: list[AuditTrackRow] = []
    passed = 0
    failed = 0
    subgenres: Counter[str] = Counter()

    for tid in track_ids:
        feat = feat_map.get(tid)
        track = track_map.get(tid)
        title = getattr(track, "title", None) if track else None
        if feat is None:
            per_track.append(
                AuditTrackRow(track_id=tid, title=title, passed=False, violations=["no features"])
            )
            failed += 1
            continue
        issues = run_audit_rules(DEFAULT_AUDIT_RULES, tid, title or "", feat)
        violations = [iss.issue for iss in issues]
        ok = not violations
        per_track.append(
            AuditTrackRow(track_id=tid, title=title, passed=ok, violations=violations)
        )
        if ok:
            passed += 1
        else:
            failed += 1
        mood_val = getattr(feat, "mood", None)
        if isinstance(mood_val, str) and mood_val:
            subgenres[mood_val] += 1

    total = len(track_ids)
    coverage = (passed / total) if total else 0.0
    return {
        "playlist_id": playlist_id,
        "total_tracks": total,
        "passed": passed,
        "failed": failed,
        "coverage": coverage,
        "per_track": per_track,
        "subgenre_distribution": dict(subgenres),
    }


@tool(
    name="ui_library_audit",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True},
    description=(
        "Prefab techno-quality audit for a playlist (or full library when omitted). "
        "Summary Cards + subgenre PieChart + DataTable with pass/fail per track."
    ),
    timeout=30.0,
)
async def ui_library_audit(
    playlist_id: Annotated[
        int | None,
        Field(description="Playlist ID; when None, audit the whole library (first 500 tracks)"),
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Column | LibraryAuditFallback:
    data = await _gather(uow, playlist_id)

    if not supports_ui(ctx):
        return fallback_or(LibraryAuditFallback, data)

    rows = [
        {
            "track_id": r.track_id,
            "title": r.title or f"#{r.track_id}",
            "status": "PASS" if r.passed else "FAIL",
            "violations": "; ".join(r.violations) or "—",
        }
        for r in data["per_track"]
    ]
    pie_data = [
        {
            "subgenre": name,
            "count": count,
            "color": SUBGENRE_COLORS.get(name, "#64748b"),
        }
        for name, count in data["subgenre_distribution"].items()
    ]

    with Column(gap=4, css_class="p-6") as view:
        Heading(f"Audit · playlist {playlist_id}" if playlist_id else "Library Audit")
        with Row(gap=4):
            Metric(label="Total", value=str(data["total_tracks"]))
            Metric(
                label="Passed",
                value=str(data["passed"]),
                trend_sentiment="positive",
            )
            Metric(
                label="Failed",
                value=str(data["failed"]),
                trend_sentiment="negative",
            )
            Metric(label="Coverage", value=f"{data['coverage'] * 100:.0f}%")
        if pie_data:
            with Card():
                CardHeader(children=[CardTitle("Subgenre distribution")])
                CardContent(
                    children=[
                        PieChart(
                            data=pie_data,
                            data_key="count",
                            name_key="subgenre",
                            show_label=True,
                            show_legend=True,
                            height=260,
                        ),
                    ]
                )
        if rows:
            DataTable(
                rows=rows,
                columns=[
                    DataTableColumn(key="track_id", header="ID", sortable=True, width="80px"),
                    DataTableColumn(key="title", header="Title", sortable=True),
                    DataTableColumn(key="status", header="Status", width="80px"),
                    DataTableColumn(key="violations", header="Violations"),
                ],
                search=True,
                paginated=len(rows) > 25,
                page_size=25,
            )
        else:
            Muted("No tracks matched the audit scope.")
    return view
