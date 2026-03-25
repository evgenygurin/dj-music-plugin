"""Import & download tools (2 tools, tag: discovery)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select

from app.config import settings
from app.mcp.dependencies import get_db_session, get_ym_client
from app.models.track import Track, TrackExternalId
from app.repositories.track import TrackRepository
from app.ym.client import YandexMusicClient


def _sanitize_filename(title: str, max_len: int = 80) -> str:
    """Sanitize string for safe filename."""
    safe = re.sub(r'[/\\:*?"<>|]', "", title)
    safe = safe.replace(" ", "_")
    safe = re.sub(r"_+", "_", safe).strip("_")[:max_len]
    return safe or "untitled"


# ── 1. import_tracks ────────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
)
async def import_tracks(
    track_refs: list[str | int],
    playlist_id: int | None = None,
    auto_analyze: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Import YM track IDs into local DB. Accepts strings or ints. Idempotent — skips existing."""
    if not track_refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    async with get_db_session() as session:
        track_repo = TrackRepository(session)
        imported = 0
        skipped = 0

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

            if ctx and imported % 10 == 0:
                await ctx.info(f"Imported {imported} tracks...")

        if ctx:
            await ctx.info(f"Import complete: {imported} new, {skipped} skipped")

        result_dict: dict[str, Any] = {
            "imported": imported,
            "skipped": skipped,
            "total_refs": len(track_refs),
        }
        if playlist_id:
            result_dict["playlist_note"] = "Use manage_playlist(add_tracks) to add to playlist"
        if auto_analyze:
            result_dict["auto_analyze_note"] = "Use analyze_batch to trigger audio analysis"
        return result_dict


# ── 2. download_tracks ──────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
    timeout=600.0,
)
async def download_tracks(
    track_refs: list[str | int],
    target_dir: str | None = None,
    skip_existing: bool = True,
    prefer_bitrate: int = 320,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Download MP3 from YM. Accepts YM track IDs (strings or ints).

    target_dir: where to save (default: settings.ym_library_path).
    skip_existing: skip if file already exists.
    prefer_bitrate: target bitrate in kbps (320, 192, 128).
    """
    if not track_refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    dest_dir = Path(target_dir or settings.ym_library_path or "~/Music/DJ/").expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped_count = 0
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

        # Get track metadata for filename
        try:
            tracks = await ym.get_tracks([ym_id])
            if tracks:
                t = tracks[0]
                artists = ", ".join(a.get("name", "?") for a in (t.artists or []))
                filename = f"{_sanitize_filename(artists)} - {_sanitize_filename(t.title)}.mp3"
            else:
                filename = f"ym_{ym_id}.mp3"
        except Exception:
            filename = f"ym_{ym_id}.mp3"

        dest_path = dest_dir / filename

        if skip_existing and dest_path.exists() and dest_path.stat().st_size > 1000:
            skipped_count += 1
            files.append({"ym_id": ym_id, "path": str(dest_path), "status": "skipped"})
            continue

        try:
            file_size = await ym.download_track(
                ym_id, str(dest_path), prefer_bitrate=prefer_bitrate
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
            if ctx:
                await ctx.info(f"Downloaded: {filename} ({file_size // 1024}KB)")
        except Exception as e:
            failed += 1
            errors.append({"ym_id": ym_id, "error": str(e)[:100]})
            if ctx:
                await ctx.warning(f"Failed: {ym_id} — {e!s:.60}")

    if ctx:
        await ctx.report_progress(total, total)
        await ctx.info(f"Done: {downloaded} downloaded, {skipped_count} skipped, {failed} failed")

    return {
        "requested": total,
        "downloaded": downloaded,
        "skipped": skipped_count,
        "failed": failed,
        "target_dir": str(dest_dir),
        "files": files[:20],
        "errors": errors[:10] if errors else [],
    }
