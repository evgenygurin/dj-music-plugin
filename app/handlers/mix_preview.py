"""Fast, isolated preview rendering for the interactive mix composer."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.db.session import get_session_factory
from app.domain.render.bar_plan import BarPlanner
from app.domain.render.beatgrid import BeatgridIO
from app.domain.render.models import BeatgridEntry, TrackInput
from app.domain.render.plan_assembler import RenderPlanner
from app.domain.render.request import RenderRequest
from app.domain.render.runner import run_render_with_progress
from app.handlers._orchestrator.stem_resolver import StemResolver
from app.repositories.unit_of_work import UnitOfWork
from app.shared.render_jobs import RENDER_JOBS

_PREVIEW_TASKS: set[asyncio.Task[Any]] = set()


async def _load_inputs(uow: Any, track_ids: list[int]) -> list[TrackInput]:
    tracks = await uow.tracks.get_many(track_ids)
    features = await uow.track_features.get_scoring_features_batch(track_ids)
    out: list[TrackInput] = []
    for tid in track_ids:
        track = tracks.get(tid)
        feat = features.get(tid)
        lib = await uow.audio_files.get_for_track(tid)
        if track is None or feat is None or lib is None:
            raise ValueError(f"track {tid} is missing metadata, features, or audio file")
        out.append(
            TrackInput(
                track_id=tid,
                yandex_id=None,
                title=track.title or f"Track {tid}",
                bpm=float(feat.bpm or 130),
                key_code=getattr(feat, "key_code", None),
                mix_in_ms=0,
                integrated_lufs=getattr(feat, "integrated_lufs", None),
                file_path=lib.file_path,
                duration_ms=getattr(track, "duration_ms", None),
            )
        )
    return out


async def start_preview(
    ctx: Any,
    uow: Any,
    *,
    session_id: str,
    track_ids: list[int],
    transition_bars: int = 8,
    body_bars: int = 8,
    stem: bool = False,
    subgenre: str | None = None,
) -> str:
    if len(track_ids) != 2:
        raise ValueError("preview requires exactly two consecutive tracks")
    job_id = f"preview-{session_id}-{uuid4().hex[:8]}"
    RENDER_JOBS.start(job_id=job_id, version_id=0, phase="queued")
    task = asyncio.create_task(
        _run_preview(
            None,
            None,
            job_id=job_id,
            session_id=session_id,
            track_ids=track_ids,
            transition_bars=transition_bars,
            body_bars=body_bars,
            stem=stem,
            subgenre=subgenre,
        )
    )
    _PREVIEW_TASKS.add(task)
    task.add_done_callback(_PREVIEW_TASKS.discard)
    return job_id


async def _run_preview(
    ctx: Any,
    uow: Any,
    *,
    job_id: str,
    session_id: str,
    track_ids: list[int],
    transition_bars: int,
    body_bars: int,
    stem: bool,
    subgenre: str | None,
) -> None:
    try:
        settings = get_settings().render.model_copy(deep=True)
        factory = get_session_factory()
        async with factory() as db_session:
            read_uow = UnitOfWork(db_session)
            inputs = await _load_inputs(read_uow, track_ids)
        workspace = Path(get_settings().delivery.output_dir) / "mix-preview" / session_id
        workspace.mkdir(parents=True, exist_ok=True)
        request = RenderRequest(
            version_id=0,
            workspace=str(workspace),
            timestamp=uuid4().hex[:8],
            out_name=f"preview-{job_id}.mp3",
            transition_bars=transition_bars,
            body_bars=body_bars,
            stem=stem,
            subgenre=subgenre,
        )
        grid: dict[int, BeatgridEntry] = {}
        grid_path = workspace / "beatgrid.json"
        if grid_path.exists():
            try:
                grid = {e.track_id: e for e in BeatgridIO.read(str(workspace))}
            except Exception:
                grid = {}
        planner = RenderPlanner()
        bar_plan = BarPlanner(settings).compute(
            inputs, grid, transition_override=transition_bars, body_override=body_bars
        )
        stem_paths = None
        if stem:
            async with factory() as db_session:
                stem_uow = UnitOfWork(db_session)
                stem_paths = await StemResolver().resolve(
                    None, stem_uow, inputs, workspace=str(workspace)
                )
            if stem_paths is None:
                request = replace(request, stem=False)
        plan = planner.assemble(settings, request, inputs, grid, bar_plan, stem_paths)
        out_path = workspace / request.out_filename
        RENDER_JOBS.update(
            job_id, phase="preview_render", total=plan.n, message="rendering 2-track preview"
        )
        started = monotonic()

        def report(progress: int, total_ms: int, message: str) -> None:
            elapsed = monotonic() - started
            eta = (elapsed * (100 - progress) / progress) if progress >= 5 else None
            text = message if eta is None else f"{message} · ~{eta:.0f}s left"
            RENDER_JOBS.update(job_id, progress=progress, total=100, message=text)

        await asyncio.to_thread(run_render_with_progress, plan, str(out_path), on_progress=report)
        RENDER_JOBS.update(
            job_id,
            phase="done",
            progress=100,
            total=100,
            out_path=str(out_path),
            done=True,
            message="preview ready",
        )
    except Exception as exc:
        RENDER_JOBS.update(
            job_id, phase="failed", error=str(exc), done=True, message="preview failed"
        )
