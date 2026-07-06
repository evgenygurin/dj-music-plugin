"""act_l5_set — UI action: bring every track of a set version to L5.

Downloads missing/stale MP3s in small batches (the download handler already
re-downloads when the DB row exists but the file is gone), then re-runs the
audio pipeline at level 5 per track. Declared ``task=True`` — this is a heavy
multi-minute pass; progress is published to RENDER_JOBS (phases
``l5-download`` / ``l5-analyze``) so the control-center panel can poll it.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.audio_file_download import audio_file_download_handler
from app.handlers.track_features_reanalyze import track_features_reanalyze_handler
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_audio_pipeline, get_provider_registry, get_uow
from app.shared.errors import NotFoundError
from app.shared.render_jobs import RENDER_JOBS
from app.shared.time import utc_timestamp_iso

try:
    from fastmcp.apps import AppConfig, app_config_to_meta_dict
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "act_l5_set requires fastmcp[apps]. Install with: uv sync --all-extras."
    ) from _exc

# Batches sized per .claude/rules/audio.md (YM rate limit vs MCP timeout).
DOWNLOAD_BATCH = 4


@tool(
    name="act_l5_set",
    tags={"namespace:ui:read", "ui"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
    meta={
        "ui": True,
        "timeout_s": 3600.0,
        **app_config_to_meta_dict(AppConfig(visibility=["app"])),
    },
    description=(
        "UI action: download + L5-reanalyze every track of a set version. Called from the UI only."
    ),
    timeout=3600.0,
    task=True,
)
async def act_l5_set(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    uow: UnitOfWork = Depends(get_uow),
    pipeline: Any = Depends(get_audio_pipeline),
    registry: Any = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    ver = await uow.set_versions.get(version_id)
    if ver is None:
        raise NotFoundError("set_version", version_id)

    items = await uow.set_versions.get_items(version_id)
    track_ids = [it.track_id for it in sorted(items, key=lambda i: i.sort_index)]

    job_id = f"l5-v{version_id}-{utc_timestamp_iso()}"
    RENDER_JOBS.start(job_id=job_id, version_id=version_id, phase="l5-download")
    RENDER_JOBS.update(job_id, total=len(track_ids))

    errors: list[dict[str, Any]] = []
    downloadable: list[int] = []
    done_count = 0
    for i in range(0, len(track_ids), DOWNLOAD_BATCH):
        batch = track_ids[i : i + DOWNLOAD_BATCH]
        result = await audio_file_download_handler(ctx, uow, {"track_ids": batch}, registry)
        errors.extend(result.get("errors", []))
        ok = {e["track_id"] for e in result.get("downloaded", [])}
        ok |= {e["track_id"] for e in result.get("skipped", [])}
        downloadable.extend(t for t in batch if t in ok)
        done_count += len(batch)
        RENDER_JOBS.update(
            job_id, progress=done_count, message=f"downloaded {done_count}/{len(track_ids)}"
        )

    RENDER_JOBS.update(job_id, phase="l5-analyze", progress=0, total=len(downloadable))
    analyzed = 0
    for n, tid in enumerate(downloadable, start=1):
        try:
            await track_features_reanalyze_handler(
                ctx, uow, {"track_id": tid, "level": 5}, pipeline, registry
            )
            analyzed += 1
        except Exception as exc:
            errors.append({"track_id": tid, "error": str(exc)})
        RENDER_JOBS.update(job_id, progress=n, message=f"analyzed {n}/{len(downloadable)}")

    RENDER_JOBS.update(job_id, done=True, message="l5 complete")
    return {
        "job_id": job_id,
        "version_id": version_id,
        "n_tracks": len(track_ids),
        "analyzed": analyzed,
        "errors": errors,
    }
