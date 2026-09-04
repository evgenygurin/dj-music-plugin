"""Backend actions for the interactive DJ mix composer."""

from __future__ import annotations

from typing import Annotated, Any, Literal, cast

from fastmcp.apps import AppConfig, app_config_to_meta_dict
from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.mix_preview import start_preview
from app.handlers.set_version_build import set_version_build_handler
from app.server.di import get_transition_scorer, get_uow
from app.shared.mix_composer import MIX_SESSIONS


async def _snapshot(session: Any, uow: Any, scorer: Any) -> dict[str, Any]:
    tracks = await uow.tracks.get_many(session.track_ids)
    features = await uow.track_features.get_scoring_features_batch(session.track_ids)
    rows: list[dict[str, Any]] = []
    for i, tid in enumerate(session.track_ids):
        track = tracks.get(tid)
        feat = features.get(tid)
        rows.append(
            {
                "position": i + 1,
                "track_id": tid,
                "title": getattr(track, "title", f"Track {tid}"),
                "bpm": getattr(feat, "bpm", None),
                "key": getattr(feat, "key_code", None),
                "energy": getattr(feat, "energy_mean", None),
                "mood": getattr(feat, "mood", None),
            }
        )
    transition = None
    if len(session.track_ids) >= 2:
        a, b = session.track_ids[-2:]
        fa, fb = features.get(a), features.get(b)
        if fa is not None and fb is not None:
            score = scorer.score(fa, fb)
            transition = {
                "from_track_id": a,
                "to_track_id": b,
                "overall": float(score.overall),
                "hard_reject": bool(score.hard_reject),
                "reason": score.reject_reason,
                "preset": score.best_transition.name if score.best_transition else None,
                "bars": int(cast(int, session.transition.get("transition_bars", 8))),
                "align": score.align.to_dict() if score.align is not None else None,
            }
    return {
        "session_id": session.session_id,
        "tracks": rows,
        "transition": transition,
        "preview_job_id": session.preview_job_id,
        "preview_path": session.preview_path,
        "transition_options": dict(session.transition),
    }


@tool(
    name="act_mix_session",
    tags={"namespace:ui:read", "ui"},
    annotations={"readOnlyHint": False, "idempotentHint": False},
    meta={"ui": True, **app_config_to_meta_dict(AppConfig(visibility=["app"]))},
    description="UI-only backend: mutate an ephemeral mix-composer session.",
)
async def act_mix_session(
    session_id: Annotated[str, Field(min_length=4)],
    action: Annotated[
        Literal["add", "remove", "set_transition", "preview", "status", "finalize", "discard"],
        Field(description="Composer action"),
    ],
    track_id: Annotated[int | None, Field(ge=1)] = None,
    transition_bars: Annotated[int | None, Field(ge=2, le=32)] = None,
    body_bars: Annotated[int | None, Field(ge=4, le=32)] = None,
    stem: bool = False,
    subgenre: str | None = None,
    set_id: int | None = None,
    label: str = "interactive-mix",
    uow: Any = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    session = MIX_SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"unknown or expired mix session: {session_id}")

    if action == "add":
        if track_id is None:
            raise ValueError("track_id is required for add")
        if track_id in session.track_ids:
            raise ValueError("track is already in the current chain")
        if len(session.track_ids) >= 30:
            raise ValueError("interactive chain is limited to 30 tracks")
        session.track_ids.append(track_id)
        session.candidates_by_source.pop(track_id, None)
        session.candidate_job_id = None
        session.candidate_error = None

    elif action == "remove":
        if len(session.track_ids) <= 1:
            raise ValueError("the first track cannot be removed")
        session.track_ids.pop()
        session.preview_job_id = None
        session.preview_path = None

    elif action == "set_transition":
        if transition_bars is not None:
            session.transition["transition_bars"] = transition_bars
        if body_bars is not None:
            session.transition["body_bars"] = body_bars
        session.transition["stem"] = stem
        if subgenre is not None:
            session.transition["subgenre"] = subgenre

    elif action == "status":
        snap = await _snapshot(session, uow, scorer)
        job = snap.get("preview_job_id")
        if job:
            from app.shared.render_jobs import RENDER_JOBS

            current = RENDER_JOBS.get(job)
            snap["preview_pending"] = bool(current and not current.done)
            if current and current.done:
                session.preview_path = current.out_path
                snap["preview_path"] = current.out_path
        else:
            snap["preview_pending"] = False
        return snap

    elif action == "preview":
        if len(session.track_ids) < 2:
            raise ValueError("add a second track before previewing")
        session.transition["transition_bars"] = transition_bars or int(
            cast(int, session.transition.get("transition_bars", 8))
        )
        session.transition["body_bars"] = body_bars or int(
            cast(int, session.transition.get("body_bars", 8))
        )
        session.transition["stem"] = stem
        if subgenre is not None:
            session.transition["subgenre"] = subgenre
        job_id = await start_preview(
            ctx,
            uow,
            session_id=session.session_id,
            track_ids=session.track_ids[-2:],
            transition_bars=int(cast(int, session.transition["transition_bars"])),
            body_bars=int(cast(int, session.transition["body_bars"])),
            stem=stem,
            subgenre=subgenre,
        )
        session.preview_job_id = job_id
        session.preview_path = None

    elif action == "finalize":
        if set_id is None:
            raise ValueError("set_id is required to finalize the chain")
        result = await set_version_build_handler(
            ctx,
            uow,
            {
                "set_id": set_id,
                "label": label,
                "track_order": list(session.track_ids),
                "generator_run_meta": {"source": "interactive_mix_composer"},
            },
        )
        MIX_SESSIONS.delete(session_id)
        return {"finalized": True, **result}

    elif action == "discard":
        MIX_SESSIONS.delete(session_id)
        return {"discarded": True, "session_id": session_id}

    return await _snapshot(session, uow, scorer)
