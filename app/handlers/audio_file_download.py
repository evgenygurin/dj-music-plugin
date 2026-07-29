"""Handler for entity_create(entity="audio_file", data={track_ids, source, ...}).

Downloads audio for each track, registers the local file. Skips existing
when the file is on disk (stale DB rows are refreshed).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from fastmcp.server.context import Context

from app.handlers._batch import BaseBatchHandler
from app.handlers._context_log import safe_report_progress
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork

_SAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def _safe(name: str, max_len: int = 120) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", name).strip()
    return re.sub(r"\s+", " ", cleaned)[:max_len] or "track"


def _hash_head(path: Path, *, bytes_: int = 65536) -> str:
    """Hash first 64KB — sufficient for dedup, cheap for big files."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(bytes_))
    return h.hexdigest()


class AudioFileDownloadHandler(BaseBatchHandler[int]):
    """Download audio files for a batch of tracks."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    def parse_ids(self, data: dict[str, Any]) -> list[int]:
        raw_ids = data.get("track_ids")
        if raw_ids is None:
            single = data.get("track_id")
            if single is None:
                raise ValueError("audio_file_download requires 'track_id' or 'track_ids'")
            raw_ids = [single]
        result = [int(x) for x in raw_ids]
        if not result:
            raise ValueError("audio_file_download requires at least one track id")
        return result

    async def _pre_check(
        self, uow: UnitOfWork, item_id: int, data: dict[str, Any], **deps: Any
    ) -> dict[str, Any] | None:
        skip_existing: bool = bool(data.get("skip_existing", True))
        if skip_existing:
            existing = await uow.audio_files.get_for_track(item_id)
            if existing is not None and Path(existing.file_path).exists():
                return {"id": item_id, "reason": "audio file already on disk"}
        return None

    async def process_one(
        self,
        ctx: Context,
        uow: UnitOfWork,
        item_id: int,
        data: dict[str, Any],
        *,
        index: int = 0,
        total: int = 1,
        **deps: Any,
    ) -> dict[str, Any]:
        source: str = data.get("source", "yandex")
        target_dir = Path(data.get("target_dir") or "/tmp/dj_audio").expanduser()
        number_files: bool = bool(data.get("number_files", True))

        await safe_report_progress(
            ctx, progress=index + 1, total=total,
            message=f"track {index+1}/{total}: resolving download info",
        )

        target_dir.mkdir(parents=True, exist_ok=True)
        provider = self._registry.get(source)

        prefix = f"{index + 1:02d}. " if number_files else ""

        platform_aliases = [source]
        if source == "yandex":
            platform_aliases.append("yandex_music")
        elif source == "yandex_music":
            platform_aliases.append("yandex")

        ext_id: str | None = None
        for platform in platform_aliases:
            ext_id = await uow.tracks.get_provider_id(item_id, platform=platform)
            if ext_id is not None:
                break

        if ext_id is None:
            raise LookupError(f"no {source} external_id for track {item_id}")

        track = await uow.tracks.get(item_id)
        title = _safe(track.title or f"track_{item_id}") if track else f"track_{item_id}"
        dest = target_dir / f"{prefix}{title} [{ext_id}].mp3"

        existing = await uow.audio_files.get_for_track(item_id)
        stale_item = (
            existing if existing is not None and not Path(existing.file_path).exists() else None
        )

        await safe_report_progress(
            ctx, progress=index + 1, total=total,
            message=f"track {index+1}/{total}: downloading {title}",
        )

        path = await provider.download_audio(ext_id, dest=dest)
        size = path.stat().st_size
        file_hash = _hash_head(path)

        if stale_item is not None:
            item = await uow.audio_files.update(
                stale_item.id,
                file_path=str(path),
                file_hash=file_hash,
                file_size=size,
            )
        else:
            item = await uow.audio_files.create(
                track_id=item_id,
                file_path=str(path),
                file_hash=file_hash,
                file_size=size,
                mime_type="audio/mpeg",
                source_app=source,
            )

        entry = {
            "track_id": item_id,
            "library_item_id": item.id,
            "path": str(path),
        }
        if stale_item is not None:
            entry["refreshed_stale_row"] = True
        return entry

    def success_key(self) -> str:
        return "downloaded"

    def summary_message(self, *, ok: int, skipped: int, errors: int) -> str:
        return f"audio_file_download: {ok} downloaded, {skipped} skipped, {errors} errors"


async def audio_file_download_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    registry: ProviderRegistry,
) -> dict[str, Any]:
    return await AudioFileDownloadHandler(registry).run(ctx, uow, data, registry=registry)
