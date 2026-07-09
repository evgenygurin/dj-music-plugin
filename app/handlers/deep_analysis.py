from __future__ import annotations

import asyncio
import logging

from app.domain.deep_analysis.models import L6AnalysisResult
from app.domain.deep_analysis.orchestrator import L6AnalysisOrchestrator
from app.providers.supabase.config import SupabaseStorageSettings
from app.providers.supabase.storage_client import SupabaseStorageClient
from app.repositories.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

_DEEP_JOBS: dict[int, L6AnalysisResult] = {}
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


async def handle_deep_analyze_track(
    track_id: int,
    uow: UnitOfWork,
    check_prereqs: bool = False,
) -> dict[str, int | str]:
    if check_prereqs:
        lib_item = await uow.audio_files.get_by_track_id(track_id)
        if lib_item is None:
            raise ValueError(f"No library_item for track {track_id}")

    run = await uow.feature_extraction_runs.create(
        track_id=track_id,
        pipeline_name="l6_deep_analysis",
        pipeline_version="1.0.0",
        status="pending",
    )

    settings = SupabaseStorageSettings()
    storage = SupabaseStorageClient(url=settings.url, key=settings.service_key)
    orchestrator = L6AnalysisOrchestrator(storage_client=storage)

    task = asyncio.create_task(_run_background(track_id, run.id, orchestrator, uow))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return {"track_id": track_id, "job_id": run.id, "status": "pending"}


async def _run_background(
    track_id: int, run_id: int, orchestrator: L6AnalysisOrchestrator, uow: UnitOfWork,
) -> None:
    try:
        result = await orchestrator.run(track_id, uow)
        _DEEP_JOBS[track_id] = result
        await uow.feature_extraction_runs.update(run_id, status="completed")
    except Exception as e:
        logger.exception(f"L6 analysis failed for track {track_id}: {e}")
        await uow.feature_extraction_runs.update(run_id, status="failed", error_message=str(e))
        _DEEP_JOBS[track_id] = L6AnalysisResult(track_id=track_id, errors=[str(e)])
