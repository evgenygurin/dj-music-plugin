"""Handler for entity_create(entity="audio_file", data={track_ids, source, ...}).

For each track_id: resolve provider external_id → call provider.download_audio →
insert DjLibraryItem + empty DjBeatgrid. Skips tracks with an existing library
item when ``skip_existing=True`` (default).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastmcp.server.context import Context

from app.v2.registry.provider import ProviderRegistry
from app.v2.repositories.unit_of_work import UnitOfWork


async def audio_file_download_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    registry: ProviderRegistry,
) -> dict[str, Any]:
    track_ids: list[int] = [int(x) for x in data["track_ids"]]
    source: str = data.get("source", "yandex")
    Path(data.get("target_dir") or "/tmp/dj_audio")
    skip_existing: bool = bool(data.get("skip_existing", True))

    provider = registry.get(source)

    downloaded: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    total = len(track_ids)
    for i, tid in enumerate(track_ids):
        track = await uow.tracks.get(tid)
        if track is None:
            errors.append({"track_id": tid, "error": "track not found"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        existing = await uow.audio_files.get_by_track_id(tid)
        if existing is not None and skip_existing:
            skipped.append({"track_id": tid, "library_item_id": existing.id})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        ext_id = await uow.provider_metadata.get_external_id(tid, platform=source)
        if ext_id is None:
            errors.append({"track_id": tid, "error": f"no {source} external_id"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        try:
            path = await provider.download_audio(ext_id)
        except Exception as exc:
            errors.append({"track_id": tid, "error": str(exc)})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        size = path.stat().st_size
        file_hash = _hash_head(path)
        item = await uow.audio_files.create(
            track_id=tid,
            file_path=str(path),
            file_hash=file_hash,
            file_size=size,
            mime_type="audio/mpeg",
            source_app=source,
        )
        downloaded.append({"track_id": tid, "library_item_id": item.id, "path": str(path)})
        await ctx.report_progress(progress=i + 1, total=total)

    await ctx.info(
        f"audio_file_download: {len(downloaded)} downloaded, "
        f"{len(skipped)} skipped, {len(errors)} errors"
    )

    return {"downloaded": downloaded, "skipped": skipped, "errors": errors}


def _hash_head(path: Path, *, bytes_: int = 65536) -> str:
    """Hash first 64KB — sufficient for dedup, cheap for big files."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(bytes_))
    return h.hexdigest()
