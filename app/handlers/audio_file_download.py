"""Handler for entity_create(entity="audio_file", data={track_ids, source, ...}).

For each track_id: resolve provider external_id → call provider.download_audio
with a target path inside ``target_dir`` (filename: ``NN. Title.mp3`` if
``prefix_index`` supplied, else ``<ext_id>.mp3``). Inserts a DjLibraryItem.
Skips tracks with an existing library item when ``skip_existing=True``.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from fastmcp.server.context import Context

from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork

_SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def _safe(name: str, max_len: int = 120) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", name).strip()
    return re.sub(r"\s+", " ", cleaned)[:max_len] or "track"


async def audio_file_download_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    registry: ProviderRegistry,
) -> dict[str, Any]:
    # ``AudioFileCreate`` lets callers pass either ``track_id`` (single) or
    # ``track_ids`` (batch); normalise both to a list here so the schema's
    # promise actually holds. Empty / missing inputs raise a clear
    # ``ValueError`` instead of a confusing ``KeyError``.
    raw_ids = data.get("track_ids")
    if raw_ids is None:
        single = data.get("track_id")
        if single is None:
            raise ValueError("audio_file_download requires 'track_id' or 'track_ids'")
        raw_ids = [single]
    track_ids: list[int] = [int(x) for x in raw_ids]
    if not track_ids:
        raise ValueError("audio_file_download requires at least one track id")
    source: str = data.get("source", "yandex")
    target_dir = Path(data.get("target_dir") or "/tmp/dj_audio").expanduser()
    skip_existing: bool = bool(data.get("skip_existing", True))
    number_files: bool = bool(data.get("number_files", True))

    target_dir.mkdir(parents=True, exist_ok=True)
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

        existing = await uow.audio_files.get_for_track(tid)
        if existing is not None and skip_existing:
            skipped.append({"track_id": tid, "library_item_id": existing.id})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        # External IDs are written under two platform labels historically —
        # the adapter name ("yandex") and the colloquial "yandex_music".
        # Probe both so old rows stay discoverable without a data migration.
        platform_aliases = [source]
        if source == "yandex":
            platform_aliases.append("yandex_music")
        elif source == "yandex_music":
            platform_aliases.append("yandex")

        ext_id: str | None = None
        for platform in platform_aliases:
            ext_id = await uow.tracks.get_provider_id(tid, platform=platform)
            if ext_id is not None:
                break

        if ext_id is None:
            errors.append({"track_id": tid, "error": f"no {source} external_id"})
            await ctx.report_progress(progress=i + 1, total=total)
            continue

        title = _safe(track.title or f"track_{tid}")
        prefix = f"{i + 1:02d}. " if number_files else ""
        # Include ``ext_id`` in the filename so two tracks with identical
        # titles — or a re-run where numbering restarts — cannot overwrite
        # each other's files while older DB rows still point at the path.
        dest = target_dir / f"{prefix}{title} [{ext_id}].mp3"

        try:
            path = await provider.download_audio(ext_id, dest=dest)
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
