"""Import & download tools (2 tools, tag: discovery)."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mcp.dependencies import get_db_session, get_track_repo, get_ym_client
from app.models.library import DjLibraryItem
from app.models.track import Track, TrackExternalId
from app.repositories.track import TrackRepository
from app.ym.client import YandexMusicClient


def _sanitize_filename(title: str, max_len: int = 80) -> str:
    """Sanitize string for safe filename."""
    safe = re.sub(r'[/\\:*?"<>|]', "", title)
    safe = safe.replace(" ", "_")
    safe = re.sub(r"_+", "_", safe).strip("_")[:max_len]
    return safe or "untitled"


# ── 1. import_tracks ─────────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
)
async def import_tracks(
    track_refs: Any = None,
    playlist_id: int | None = None,
    auto_analyze: bool = False,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Import YM track IDs into local DB. Accepts strings or ints. Idempotent — skips existing."""
    from app.core.parsing import ensure_list

    track_refs = ensure_list(track_refs)
    if not track_refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    imported = 0
    skipped = 0
    imported_ids: list[str] = []
    id_mapping: dict[str, int] = {}

    for ref in track_refs:
        ym_id = str(ref).strip()
        if not ym_id:
            continue

        stmt = select(TrackExternalId).where(
            TrackExternalId.platform == "yandex_music",
            TrackExternalId.external_id == ym_id,
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            skipped += 1
            continue

        track = Track(title=f"YM:{ym_id}", status=0)
        track = await track_repo.create(track)
        await session.flush()

        ext_id = TrackExternalId(track_id=track.id, platform="yandex_music", external_id=ym_id)
        session.add(ext_id)
        imported += 1
        imported_ids.append(ym_id)
        id_mapping[ym_id] = track.id

        if ctx and imported % 10 == 0:
            await ctx.info(f"Imported {imported} tracks...")

    # Enrich with YM metadata (batch fetch)
    enriched = 0
    if imported_ids:
        try:
            ym_tracks = await ym.get_tracks(imported_ids)
            ym_by_id = {str(t.id): t for t in ym_tracks}

            from app.models.platform import YandexMetadata

            for ym_id_str, local_track_id in id_mapping.items():
                ym_track = ym_by_id.get(ym_id_str)
                if not ym_track:
                    continue

                local_track = await track_repo.get_by_id(local_track_id)
                if local_track and local_track.title.startswith("YM:"):
                    artists = ", ".join(a.get("name", "?") for a in (ym_track.artists or []))
                    local_track.title = (
                        f"{artists} - {ym_track.title}" if artists else ym_track.title
                    )
                    if ym_track.duration_ms:
                        local_track.duration_ms = ym_track.duration_ms
                    await session.flush()

                albums = ym_track.albums or []
                album = albums[0] if albums else {}
                meta = YandexMetadata(
                    track_id=local_track_id,
                    yandex_track_id=ym_id_str,
                    album_id=str(album.get("id", "")) if album else None,
                    album_title=album.get("title") if album else None,
                    album_genre=album.get("genre") if album else None,
                    album_year=album.get("year") if album else None,
                    duration_ms=ym_track.duration_ms,
                    cover_uri=ym_track.cover_uri,
                    explicit=ym_track.explicit,
                )
                session.add(meta)
                enriched += 1

            await session.flush()
        except Exception as e:
            if ctx:
                await ctx.info(f"YM metadata enrichment skipped: {e}")

    if ctx:
        await ctx.info(f"Import complete: {imported} new, {skipped} skipped, {enriched} enriched")

    result_dict: dict[str, Any] = {
        "imported": imported,
        "skipped": skipped,
        "enriched": enriched,
        "total_refs": len(track_refs),
    }
    if playlist_id:
        result_dict["playlist_note"] = "Use manage_playlist(add_tracks) to add to playlist"
    if auto_analyze:
        result_dict["auto_analyze_note"] = "Use analyze_batch to trigger audio analysis"
    return result_dict


# ── 2. download_tracks ───────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
    timeout=600.0,
    task=True,
)
async def download_tracks(
    track_refs: Any = None,
    target_dir: str | None = None,
    skip_existing: bool = True,
    prefer_bitrate: int = 320,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Download MP3 from YM and link to library. Accepts YM track IDs.

    Downloads files, creates DjLibraryItem records (so analyze_track finds them).
    target_dir: where to save (default: settings.ym_library_path).
    skip_existing: skip if file already exists.
    prefer_bitrate: target bitrate in kbps (320, 192, 128).
    """
    from app.core.parsing import ensure_list

    track_refs = ensure_list(track_refs)
    if not track_refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    dest_dir = Path(target_dir or settings.ym_library_path or "~/Music/DJ/").expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped_count = 0
    linked = 0
    failed = 0
    errors: list[dict[str, str]] = []
    files: list[dict[str, Any]] = []

    total = len(track_refs)
    for i, ref in enumerate(track_refs):
        ym_id = str(ref).strip()
        if not ym_id:
            continue

        if ctx:
            await ctx.report_progress(i, total)

        # Resolve filename from YM metadata
        try:
            ym_tracks = await ym.get_tracks([ym_id])
            if ym_tracks:
                t = ym_tracks[0]
                artists = ", ".join(str(a.get("name", "?")) for a in (t.artists or []))
                filename = f"{_sanitize_filename(artists)} - {_sanitize_filename(t.title)}.mp3"
            else:
                filename = f"ym_{ym_id}.mp3"
        except Exception:
            filename = f"ym_{ym_id}.mp3"

        dest_path = dest_dir / filename

        # Skip existing files (but still link to library)
        if skip_existing and dest_path.exists() and dest_path.stat().st_size > 1000:
            skipped_count += 1
            files.append(
                {
                    "ym_id": ym_id,
                    "path": str(dest_path),
                    "status": "skipped",
                }
            )
            linked += await _link_file_to_track(session, ym_id, dest_path)
            continue

        # Download
        try:
            file_size = await ym.download_track(
                ym_id,
                str(dest_path),
                prefer_bitrate=prefer_bitrate,
            )
            downloaded += 1
            files.append(
                {
                    "ym_id": ym_id,
                    "path": str(dest_path),
                    "size_bytes": file_size,
                    "status": "downloaded",
                }
            )
            linked += await _link_file_to_track(session, ym_id, dest_path)
            if ctx:
                await ctx.info(f"Downloaded: {filename} ({file_size // 1024}KB)")
        except Exception as e:
            failed += 1
            errors.append({"ym_id": ym_id, "error": str(e)[:100]})
            if ctx:
                await ctx.warning(f"Failed: {ym_id} — {str(e)[:60]}")

    await session.flush()

    if ctx:
        await ctx.report_progress(total, total)
        await ctx.info(
            f"Done: {downloaded} downloaded, {skipped_count} skipped, "
            f"{linked} linked, {failed} failed"
        )

    return {
        "requested": total,
        "downloaded": downloaded,
        "skipped": skipped_count,
        "linked_to_library": linked,
        "failed": failed,
        "target_dir": str(dest_dir),
        "files": files[:20],
        "errors": errors[:10] if errors else [],
    }


async def _link_file_to_track(
    session: AsyncSession,
    ym_id: str,
    file_path: Path,
) -> int:
    """Find local track by YM ID, create DjLibraryItem if missing.

    Returns 1 if linked, 0 if not (no track found or already linked).
    """
    # Find local track_id by YM external ID
    stmt = select(TrackExternalId.track_id).where(
        TrackExternalId.platform == "yandex_music",
        TrackExternalId.external_id == ym_id,
    )
    result = await session.execute(stmt)
    track_id = result.scalar_one_or_none()
    if track_id is None:
        return 0

    # Check if library item already exists
    existing = await session.execute(
        select(DjLibraryItem.id).where(DjLibraryItem.track_id == track_id)
    )
    if existing.scalar_one_or_none() is not None:
        return 0

    # Compute file hash (MD5 is fine for dedup, not security)
    file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()

    item = DjLibraryItem(
        track_id=track_id,
        file_path=str(file_path),
        file_hash=file_hash,
        file_size=file_path.stat().st_size,
        mime_type="audio/mpeg",
        source_app="ym_download",
    )
    session.add(item)
    return 1
