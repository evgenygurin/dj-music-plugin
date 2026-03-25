"""Import & download tools (2 tools, tag: discovery)."""

from __future__ import annotations

from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select

from app.config import settings
from app.mcp.dependencies import get_db_session
from app.models.track import Track, TrackExternalId
from app.repositories.track import TrackRepository

# ── 4. import_tracks ────────────────────────────────


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


# ── 5. download_tracks ──────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
    timeout=300.0,
)
async def download_tracks(
    track_refs: list[str | int],
    target_dir: str | None = None,
    skip_existing: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Download MP3 from YM for given track refs. Accepts strings or ints."""
    if not track_refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    if ctx:
        await ctx.info(f"Download requested for {len(track_refs)} tracks")

    return {
        "requested": len(track_refs),
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
        "target_dir": target_dir or settings.ym_library_path or "~/Music/DJ/",
        "message": "MP3 download requires audio pipeline integration (Phase 4)",
    }
