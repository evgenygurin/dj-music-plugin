"""stems_separate — FastMCP Task for 5-stem separation (M2 8GB safe).

Batched separation with ``ctx.report_progress`` per track, ``asyncio.Semaphore(1)``
(serialize — unified memory on M2 8GB OOMs with 2 parallel Demucs runs),
``asyncio.to_thread`` (don't block MCP loop), and per-track GC/MPS cleanup.

Uses the 3-tier resolver (mlx → onnx → torch) via ``get_runner``.
Cache: ``sha256(path)[:12] / model / stem.flac`` — not changed (resolver + runner).
"""

from __future__ import annotations

import asyncio
import gc
from pathlib import Path
from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers._context_log import safe_info, safe_report_progress
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow

# Serialize separation — same invariant as stem_resolver._SEM (M2 8GB unified
# memory). Keep a local semaphore so a standalone ``stems_separate`` call and
# a concurrent ``render_mixdown(..., stem=True)`` don't race on the runner:
# two Demucs/MPS graphs at once OOMs on 8GB.
_STEM_TASK_SEM = asyncio.Semaphore(1)


async def _resolve_track_path(uow: Any, track_id: int) -> Path | None:
    """Resolve ``track_id`` → local audio file path via UoW.

    Tries ``uow.tracks.get`` / ``uow.audio_files.get`` (attributes vary by
    fixture), then the ``DjLibraryItem`` table via ``uow.session``. Returns
    ``None`` when not found — caller logs and skips.
    """
    for repo_name in ("tracks", "audio_files", "dj_library_items"):
        repo = getattr(uow, repo_name, None)
        if repo is None or not hasattr(repo, "get"):
            continue
        try:
            row = await repo.get(track_id)
        except Exception:
            continue
        if row is None:
            continue
        # row may be ORM object, dict, or Pydantic view
        for pfield in ("file_path", "path", "local_path", "filepath", "filePath"):
            val = getattr(row, pfield, None) if not isinstance(row, dict) else row.get(pfield)
            if isinstance(val, str) and val:
                return Path(val)
            if isinstance(val, Path):
                return val

    # Fallback: query DjLibraryItem directly via session (resolver's path)
    try:
        session = getattr(uow, "session", None)
        if session is not None:
            from sqlalchemy import select

            from app.models.audio_file import DjLibraryItem

            stmt = select(DjLibraryItem.file_path).where(DjLibraryItem.track_id == track_id)
            res = await session.execute(stmt)
            fp = res.scalar_one_or_none()
            if isinstance(fp, str) and fp:
                return Path(fp)
    except Exception:
        pass

    return None


@tool(
    name="stems_separate",
    tags={"namespace:stems", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": False},
    description=(
        "Separate tracks into 5 electronic-music stems (vocals, drums, bass, "
        "harmonic, percussion). 3-tier runtime: mlx → onnx-coreml → torch-mps "
        "(auto-detected, override via DJ_STEMS_RUNTIME). Serialized with "
        "Semaphore(1) for M2 8GB, runs off-thread via to_thread so the MCP "
        "loop stays responsive. Reports progress per track and honours "
        "cancellation. Heavy — background task."
    ),
    meta={"timeout_s": 1800.0},
    timeout=1800.0,
    task=True,
)
async def stems_separate(
    track_ids: Annotated[
        list[int],
        Field(description="Track IDs to separate (1+ ids, order preserved)"),
    ],
    ctx: Context = CurrentContext(),
    uow: UnitOfWork = Depends(get_uow),
) -> dict[str, Any]:
    """FastMCP Task: batch stem separation with progress + cancel.

    Returns:
        ``{"stems": {track_id: {stem: path}}, "errors": [...]}`` — ``stems``
        keys are strings (JSON object keys). Each stem dict has the canonical
        5 keys when successful.
    """
    if not track_ids:
        raise ValueError("track_ids must be non-empty")

    # Validate ids eagerly (so bad input fails before any DSP)
    for tid in track_ids:
        if not isinstance(tid, int) or tid < 1:
            raise ValueError(f"invalid track_id {tid!r}: must be int >=1")

    try:
        from app.audio.deep import get_runner
        from app.config import get_settings
        from app.config.stems import StemsConfig
        from app.domain.render.models import STEM_ORDER
        from app.handlers._orchestrator.stem_resolver import _expand_stem_paths, _find_cached_stems
    except ImportError as exc:  # pragma: no cover
        await safe_info(ctx, f"stem separation unavailable ({exc})")
        raise

    cfg = StemsConfig()
    try:
        runner = get_runner(cfg)
    except Exception as exc:  # pragma: no cover
        await safe_info(ctx, f"stem separation unavailable ({exc})")
        raise

    settings = get_settings()
    # Reuse resolver's scan root: generated-sets/render/*/stems — dedicate a
    # subdir so ``_find_cached_stems`` glob finds past Task runs without
    # colliding with versioned workspaces.
    workspace = str(Path(settings.delivery.output_dir) / "render" / "stems_task")
    cache_root = Path(workspace) / "stems"

    total = len(track_ids)
    stems_out: dict[str, dict[str, str]] = {}
    errors: list[dict[str, Any]] = []

    # Initial progress (0/total) — lets clients show a bar immediately
    await safe_report_progress(
        ctx, progress=0, total=total, message=f"stems_separate: {total} tracks queued"
    )

    for i, tid in enumerate(track_ids):
        # Cooperative cancel point — if the client cancelled the MCP task,
        # the surrounding asyncio Task is cancelled and the next await will
        # raise CancelledError. Check explicitly too for prompt abort.
        try:
            cur = asyncio.current_task()
            if cur is not None and cur.cancelled():
                raise asyncio.CancelledError()
        except asyncio.CancelledError:
            await safe_info(ctx, f"stems_separate cancelled at {tid} ({i}/{total})")
            raise

        await safe_report_progress(
            ctx, progress=i, total=total, message=f"separating {tid} ({i + 1}/{total})"
        )

        input_file = await _resolve_track_path(uow, tid)
        if input_file is None:
            msg = f"track {tid} not found or has no file_path"
            await safe_info(ctx, msg)
            errors.append({"track_id": tid, "error": msg})
            continue
        if not input_file.exists():
            msg = f"missing audio for track {tid}: {input_file}"
            await safe_info(ctx, msg)
            errors.append({"track_id": tid, "error": msg})
            continue

        # Cache hit — reuse flac stems from any past render/task workspace
        cached = _find_cached_stems(input_file)
        if cached is not None:
            stems_out[str(tid)] = cached
            await safe_report_progress(
                ctx, progress=i + 1, total=total, message=f"cached {tid} ({i + 1}/{total})"
            )
            continue

        await safe_info(ctx, f"stems_separate: separating track {tid} ({input_file.name})...")

        try:
            async with _STEM_TASK_SEM:
                # Re-check cancellation while waiting on semaphore
                try:
                    cur2 = asyncio.current_task()
                    if cur2 is not None and cur2.cancelled():
                        raise asyncio.CancelledError()
                except asyncio.CancelledError:
                    await safe_info(ctx, f"stems_separate cancelled while queued for {tid}")
                    raise

                raw = await asyncio.to_thread(
                    runner,
                    input_file,
                    cache_root,
                    model=cfg.model,
                    flac=True,
                )

                # Free unified memory promptly (M2 8GB)
                try:
                    gc.collect()
                    try:
                        import torch

                        if torch.backends.mps.is_available():
                            torch.mps.empty_cache()
                    except Exception:
                        pass
                except Exception:
                    pass

        except asyncio.CancelledError:
            await safe_info(ctx, f"stems_separate cancelled during {tid}")
            raise
        except Exception as exc:
            msg = f"separation failed for track {tid}: {exc}"
            await safe_info(ctx, msg)
            errors.append({"track_id": tid, "error": str(exc)})
            continue

        mapped = _expand_stem_paths(raw)
        missing = set(STEM_ORDER) - set(mapped)
        if missing:
            msg = f"runner output missing stems {sorted(missing)} for track {tid}"
            await safe_info(ctx, msg)
            errors.append({"track_id": tid, "error": msg})
            continue

        stems_out[str(tid)] = mapped

        # Extra GC between tracks (outside semaphore, still frees memory)
        try:
            gc.collect()
            try:
                import torch

                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
            except Exception:
                pass
        except Exception:
            pass

        await safe_report_progress(
            ctx, progress=i + 1, total=total, message=f"done {tid} ({i + 1}/{total})"
        )

    await safe_report_progress(ctx, progress=total, total=total, message="stems_separate done")
    await safe_info(
        ctx, f"stems_separate: {len(stems_out)}/{total} tracks ready, {len(errors)} errors"
    )

    return {"stems": stems_out, "errors": errors, "total": total}
