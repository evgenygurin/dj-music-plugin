"""Interactive track-by-track DJ set composer.

The model opens the composer with one track; the UI then exposes ranked next
tracks, a transition score, editable transition controls and short previews.
No full-set render is performed until the user explicitly finalizes.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Annotated, Any

from fastmcp.apps import AppConfig, app_config_to_meta_dict
from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from prefab_ui.actions import OpenLink, SetInterval, SetState, ShowToast
from prefab_ui.actions.mcp import CallTool
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Audio,
    Badge,
    Button,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Column,
    DataTable,
    DataTableColumn,
    Heading,
    Label,
    Muted,
    Progress,
    Row,
    Select,
    SelectOption,
    Slider,
    Slot,
)
from pydantic import Field
from sqlalchemy import select

from app.domain.transition.components import score_bpm, score_energy
from app.domain.transition.dj_mixing import (
    AlignmentScore,
    compute_alignment,
    generate_transition_cues,
    select_transition_bars,
)
from app.domain.transition.hard_constraints import check_hard_constraints
from app.domain.transition.scorer import TransitionScorer
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_transition_scorer, get_uow
from app.shared.features import TrackFeatures
from app.shared.mix_composer import MIX_SESSIONS
from app.shared.render_jobs import RENDER_JOBS


def _file_audio_uri(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or p.stat().st_size > 2_000_000:
        return None
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:audio/mpeg;base64,{encoded}"


async def _candidates(
    uow: UnitOfWork, scorer: Any, source_id: int, limit: int = 8
) -> list[dict[str, Any]]:
    source = (await uow.track_features.get_scoring_features_batch([source_id])).get(source_id)
    if source is None or source.bpm is None:
        return []
    bpm_lo, bpm_hi = float(source.bpm) * 0.92, float(source.bpm) * 1.08
    rows = (
        (
            await uow.session.execute(
                select(TrackAudioFeaturesComputed)
                .where(TrackAudioFeaturesComputed.track_id != source_id)
                .where(TrackAudioFeaturesComputed.bpm.between(bpm_lo, bpm_hi))
                .where(TrackAudioFeaturesComputed.bpm.is_not(None))
                .order_by(TrackAudioFeaturesComputed.bpm_confidence.desc().nullslast())
                .limit(500)
            )
        )
        .scalars()
        .all()
    )
    features = {row.track_id: TrackFeatures.from_db(row) for row in rows}
    # Cheap-first filter: BPM Gauss + energy Gauss (no Neural Mix, no
    # alignment). This is intentionally identical to the pre-Cell 16
    # composer so existing UX semantics are preserved.
    cheap: list[tuple[float, int, Any]] = []
    for tid, target in features.items():
        gate = check_hard_constraints(source, target)
        if gate is not None and gate.hard_reject:
            continue
        rank = 0.65 * score_bpm(source, target) + 0.35 * score_energy(source, target)
        cheap.append((float(rank), tid, target))
    cheap.sort(reverse=True, key=lambda x: x[0])
    # Cell 16 cheap→deep ordering: only the top-N survivors of the
    # BPM+energy gate get the four-component alignment computed.
    # Neural Mix stems are even more expensive and stay on the
    # ``scorer.score`` path below — the cheap DJ-aware alignment runs
    # *before* the full stem pass so we can rank-align first and only
    # then pay the Neural Mix cost.
    align_shortlist: list[tuple[int, Any]] = [
        (tid, target) for _rank, tid, target in cheap[:80]
    ]
    align_scores: dict[int, AlignmentScore] = {}
    for tid, target in align_shortlist:
        align_scores[tid] = compute_alignment(source, target, transition_bars=16)
    scored: list[dict[str, Any]] = []
    for tid, target in align_shortlist:
        score = scorer.score(source, target)
        if score.hard_reject:
            continue
        align = align_scores.get(tid)
        transition_bars = select_transition_bars()
        cue_points = [
            cue.to_dict()
            for cue in generate_transition_cues(
                track_id=tid,
                features=target,
                role="mix_in",
                n_candidates=4,
                target_bars=transition_bars,
            )
        ]
        scored.append(
            {
                "track_id": tid,
                "overall": round(float(score.overall), 3),
                "bpm": getattr(target, "bpm", None),
                "key": getattr(target, "key_code", None),
                "energy": getattr(target, "energy_mean", None),
                "align": align.to_dict() if align is not None else None,
                "transition_bars": transition_bars,
                "cue_points": cue_points,
            }
        )
    # Cheap alignment rank: combine the cheap BPM+energy rank with the
    # 4-component alignment overall so the cheap-first path stays
    # meaningful. The user-facing ``overall`` stays the six-component
    # stem-aware score.
    if align_scores:
        cheap_rank = {tid: r for r, tid, _ in cheap[:80]}
        for entry in scored:
            tid = entry["track_id"]
            align_overall = (
                entry["align"]["overall"] if entry.get("align") else 0.0
            )
            entry["align_overall"] = round(
                0.5 * cheap_rank.get(tid, 0.0) + 0.5 * align_overall, 4
            )
    else:
        for entry in scored:
            entry["align_overall"] = 0.0
    scored.sort(key=lambda x: x.get("align_overall", 0.0), reverse=True)
    top = scored[:limit]
    titles = await uow.tracks.get_many([x["track_id"] for x in top])
    for row in top:
        row["title"] = getattr(titles.get(row["track_id"]), "title", f"Track {row['track_id']}")
    return top


async def _panel_data(session_id: str, uow: UnitOfWork, scorer: Any) -> dict[str, Any]:
    session = MIX_SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"unknown or expired mix session: {session_id}")
    snapshot = await _snapshot(session, uow, scorer)
    source = session.track_ids[-1]
    if source not in session.candidates_by_source:
        _ensure_candidate_job(session)
    snapshot["candidates"] = session.candidates_by_source.get(source, [])
    snapshot["candidate_pending"] = bool(
        session.candidate_job_id and source not in session.candidates_by_source
    )
    snapshot["candidate_error"] = session.candidate_error
    job = RENDER_JOBS.get(session.preview_job_id) if session.preview_job_id else None
    snapshot["preview_pending"] = bool(job and not job.done)
    if job and job.done:
        session.preview_path = job.out_path
        snapshot["preview_path"] = job.out_path
    return snapshot


async def _snapshot(session: Any, uow: UnitOfWork, scorer: Any) -> dict[str, Any]:
    tracks = await uow.tracks.get_many(session.track_ids)
    features = await uow.track_features.get_scoring_features_batch(session.track_ids)
    rows = []
    for i, tid in enumerate(session.track_ids):
        feat = features.get(tid)
        rows.append(
            {
                "position": i + 1,
                "track_id": tid,
                "title": getattr(tracks.get(tid), "title", f"Track {tid}"),
                "bpm": getattr(feat, "bpm", None),
                "key": getattr(feat, "key_code", None),
            }
        )
    transition = None
    if len(session.track_ids) >= 2:
        a, b = session.track_ids[-2:]
        fa, fb = features.get(a), features.get(b)
        if fa is not None and fb is not None:
            s = scorer.score(fa, fb)
            transition = {
                "from_track_id": a,
                "to_track_id": b,
                "overall": float(s.overall),
                "hard_reject": bool(s.hard_reject),
                "reason": s.reject_reason,
                "preset": s.best_transition.name if s.best_transition else None,
                "align": s.align.to_dict() if s.align is not None else None,
            }
    return {
        "session_id": session.session_id,
        "tracks": rows,
        "transition": transition,
        "preview_job_id": session.preview_job_id,
        "preview_path": session.preview_path,
        "transition_options": dict(session.transition),
    }


def _refresh(session: str) -> CallTool:
    return CallTool(
        "ui_mix_composer_panel",
        arguments={"session_id": session},
        on_success=SetState("panel", "{{ $result }}"),
    )


def _action(session: str, action: str, **kwargs: Any) -> CallTool:
    args = {"session_id": session, "action": action, **kwargs}
    return CallTool("act_mix_session", arguments=args)


def _panel_view(data: dict[str, Any], set_id: int | None) -> Any:
    sid = data["session_id"]
    transition = data.get("transition")
    candidates = data.get("candidates") or []
    preview = data.get("preview_path")
    with Column(gap=4) as panel:
        with Card():
            CardHeader(children=[CardTitle("Current chain")])
            with CardContent():
                DataTable(
                    rows=data["tracks"],
                    columns=[
                        DataTableColumn(key="position", header="#"),
                        DataTableColumn(key="title", header="Track"),
                        DataTableColumn(key="bpm", header="BPM"),
                        DataTableColumn(key="key", header="Key"),
                    ],
                )
                Button(
                    "Undo last",
                    variant="outline",
                    onClick=[
                        _action(
                            sid,
                            "remove",
                        ),
                        _refresh(sid),
                    ],
                )
        if transition:
            with Card():
                CardHeader(children=[CardTitle("Last transition")])
                with CardContent():
                    Badge(
                        label="HARD REJECT" if transition["hard_reject"] else "PASS",
                        variant="destructive" if transition["hard_reject"] else "success",
                    )
                    Muted(
                        f"score {transition['overall']:.2f} · preset {transition['preset'] or 'auto'}"
                    )
                    if transition["reason"]:
                        Muted(transition["reason"])
                    Label("Preview mode")
                    with Select(name="stem_mode", value="false", placeholder="Render mode"):
                        SelectOption(value="false", label="Classic (fast)", selected=True)
                        SelectOption(value="true", label="4/5-stem (slower)")
                    Label("Transition bars")
                    Slider(
                        name="transition_bars",
                        min=2,
                        max=32,
                        step=2,
                        value=data["transition_options"].get("transition_bars", 8),
                    )
                    Label("Body bars")
                    Slider(
                        name="body_bars",
                        min=4,
                        max=32,
                        step=4,
                        value=data["transition_options"].get("body_bars", 8),
                    )
                    Button(
                        "Apply transition settings",
                        variant="secondary",
                        onClick=[
                            _action(
                                sid,
                                "set_transition",
                                transition_bars="{{ transition_bars }}",
                                body_bars="{{ body_bars }}",
                                stem="{{ stem_mode }}",
                            ),
                            _refresh(sid),
                        ],
                    )
                    Button(
                        "Preview this transition",
                        onClick=[
                            _action(
                                sid,
                                "preview",
                                transition_bars="{{ transition_bars }}",
                                body_bars="{{ body_bars }}",
                                stem="{{ stem_mode }}",
                            ),
                            _refresh(sid),
                            SetInterval(3000, count=60, onTick=_refresh(sid)),
                        ],
                    )
        if preview:
            with Card():
                CardHeader(children=[CardTitle("Preview")])
                with CardContent():
                    uri = _file_audio_uri(preview)
                    if uri:
                        Audio(src=uri, controls=True)
                    Button(
                        "Open preview file",
                        variant="outline",
                        onClick=OpenLink(f"file://{preview}"),
                    )
        elif data.get("preview_pending"):
            with Card():
                CardHeader(children=[CardTitle("Rendering preview")])
                with CardContent():
                    job = (
                        RENDER_JOBS.get(data.get("preview_job_id"))
                        if data.get("preview_job_id")
                        else None
                    )
                    done = job.progress if job else 0
                    total = job.total if job else 0
                    Progress(value=(done / total * 100) if total else 5)
                    Muted(job.message if job else "Starting preview…")
        with Card():
            CardHeader(children=[CardTitle("Choose the next track")])
            with CardContent():
                if data.get("candidate_pending"):
                    Progress(value=25)
                    Muted("Finding compatible tracks… this runs in the background.")
                elif data.get("candidate_error"):
                    Muted(f"Suggestion scan failed: {data['candidate_error']}")
                else:
                    Muted(
                        "Suggestions are ranked by BPM, key, energy and stem-aware transition quality."
                    )
                for c in candidates:
                    Button(
                        f"Add #{c['track_id']} · {c['title']} · {c['overall']:.2f}",
                        variant="outline",
                        onClick=[_action(sid, "add", track_id=c["track_id"]), _refresh(sid)],
                    )
        with Row(gap=2):
            if set_id is not None:
                Button(
                    "Save set version",
                    variant="success",
                    onClick=[
                        _action(sid, "finalize", set_id=set_id, label="interactive-mix"),
                        ShowToast("Set version saved", variant="success"),
                    ],
                )
            Button(
                "Discard session",
                variant="destructive",
                onClick=[_action(sid, "discard"), ShowToast("Composer discarded")],
            )
    return panel


@tool(
    name="ui_mix_composer_panel",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, **app_config_to_meta_dict(AppConfig(visibility=["app"]))},
    description="UI helper for the interactive DJ mix composer.",
    timeout=30.0,
)
async def ui_mix_composer_panel(
    session_id: Annotated[str, Field(min_length=4)],
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> Column:
    data = await _panel_data(session_id, uow, scorer)
    return _panel_view(
        data, MIX_SESSIONS.get(session_id).set_id if MIX_SESSIONS.get(session_id) else None
    )


@tool(
    name="ui_mix_composer",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": {"resourceUri": "ui://prefab/renderer.html", "visibility": ["model"]}},
    description=(
        "Interactive DJ set composer: start from one track, choose ranked next tracks, "
        "preview only the current transition, edit it, and save only when satisfied."
    ),
    timeout=30.0,
)
async def ui_mix_composer(
    first_track_id: Annotated[int, Field(ge=1, description="Track to start the set with")],
    set_id: Annotated[int | None, Field(ge=1, description="Existing set to save into")] = None,
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> PrefabApp:
    if (await uow.tracks.get(first_track_id)) is None:
        raise ValueError(f"track {first_track_id} not found")
    session = MIX_SESSIONS.create(first_track_id, set_id=set_id)
    data = await _panel_data(session.session_id, uow, scorer)
    poll = SetInterval(2000, count=30, onTick=_refresh(session.session_id))
    with Column(gap=4, css_class="p-6", onMount=poll) as view:
        Heading("DJ Mix Composer")
        Muted(
            "Build incrementally. Pick a suggested next track, preview the two-track "
            "transition, change the transition length, and repeat. Full-set render is final only."
        )
        Slot(name="panel")
    return PrefabApp(view=view, state={"panel": _panel_view(data, set_id)})


_CANDIDATE_TASKS: set[Any] = set()


async def _candidate_worker(session_id: str, source_id: int, job_id: str) -> None:
    try:
        from app.db.session import get_session_factory

        async with get_session_factory()() as db:
            uow = UnitOfWork(db)
            candidates = await _candidates(uow, TransitionScorer(), source_id)
        session = MIX_SESSIONS.get(session_id)
        if session is not None:
            session.candidates_by_source[source_id] = candidates
            session.candidate_job_id = None
            session.candidate_error = None
        RENDER_JOBS.update(
            job_id,
            done=True,
            phase="done",
            progress=1,
            total=1,
            message="next-track suggestions ready",
        )
    except Exception as exc:
        session = MIX_SESSIONS.get(session_id)
        if session is not None:
            session.candidate_error = str(exc)
        RENDER_JOBS.update(
            job_id, done=True, phase="failed", error=str(exc), message="candidate scan failed"
        )


def _ensure_candidate_job(session: Any) -> None:
    source_id = session.track_ids[-1]
    if source_id in session.candidates_by_source or session.candidate_job_id:
        return
    job_id = f"candidates-{session.session_id}-{source_id}"
    session.candidate_job_id = job_id
    RENDER_JOBS.start(job_id=job_id, version_id=0, phase="candidate_scan")
    task = __import__("asyncio").create_task(
        _candidate_worker(session.session_id, source_id, job_id)
    )
    _CANDIDATE_TASKS.add(task)
    task.add_done_callback(_CANDIDATE_TASKS.discard)
