"""Discovery & download tools (3 tools, tag: discovery)."""

from __future__ import annotations

from typing import Any

from docket import CurrentDocket, Docket
from fastmcp.dependencies import Progress
from fastmcp.server.context import Context
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, TrackExternalId
from app.repositories.track import TrackRepository
from app.server import mcp

# ── Helpers ──────────────────────────────────────────


async def _get_session(ctx: Context | None) -> AsyncSession:
    """Get async session from lifespan context."""
    if ctx is None:
        raise RuntimeError("Context required — tools must be called via MCP")
    factory = ctx.lifespan_context["db_session_factory"]
    return factory()


# ── 1. find_similar_tracks ──────────────────────────


@mcp.tool(
    tags={"discovery"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def find_similar_tracks(
    track_id: int,
    strategy: str = "ym",
    limit: int = 10,
    bpm_tolerance: float = 5.0,
    key_compatible: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find similar tracks by strategy: ym, embedding, llm, combined."""
    valid_strategies = {"ym", "embedding", "llm", "combined"}
    if strategy not in valid_strategies:
        return {
            "error": f"Unknown strategy: {strategy}. Valid: {', '.join(sorted(valid_strategies))}"
        }

    async with await _get_session(ctx) as session:
        track_repo = TrackRepository(session)
        track = await track_repo.get_by_id(track_id)
        if track is None:
            return {"error": f"Track {track_id} not found"}

        if strategy == "ym":
            # Stub: YM similar tracks API will be integrated later
            # For now return empty results with the correct shape
            return {
                "track_id": track_id,
                "track_title": track.title,
                "strategy": strategy,
                "similar": [],
                "message": "YM similar tracks integration pending — requires ym_client",
            }

        if strategy == "embedding":
            return {
                "track_id": track_id,
                "track_title": track.title,
                "strategy": strategy,
                "similar": [],
                "message": (
                    "Embedding similarity requires audio feature vectors — not yet implemented"
                ),
            }

        if strategy == "llm":
            return {
                "track_id": track_id,
                "track_title": track.title,
                "strategy": strategy,
                "similar": [],
                "message": "LLM similarity requires sampling — not yet implemented",
            }

        # combined
        return {
            "track_id": track_id,
            "track_title": track.title,
            "strategy": strategy,
            "similar": [],
            "message": "Combined strategy aggregates ym + embedding + llm — not yet implemented",
        }


# ── 2. import_tracks ────────────────────────────────


@mcp.tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
)
async def import_tracks(
    track_refs: list[str],
    playlist_id: int | None = None,
    auto_analyze: bool = False,
    progress: Progress = Progress(),
    docket: Docket = CurrentDocket(),
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Import YM track IDs into local DB. Idempotent — skips existing.

    If auto_analyze=True, schedules background analysis for imported tracks.
    """
    if not track_refs:
        return {"error": "track_refs is required (list of YM track IDs)"}

    await progress.set_total(len(track_refs))
    await progress.set_message("Starting import...")

    async with await _get_session(ctx) as session:
        track_repo = TrackRepository(session)

        imported = 0
        imported_ids: list[int] = []
        skipped = 0
        errors: list[str] = []

        for idx, ref in enumerate(track_refs):
            ym_id = ref.strip()
            if not ym_id:
                continue

            # Check if already imported
            stmt = select(TrackExternalId).where(
                TrackExternalId.platform == "yandex_music",
                TrackExternalId.external_id == ym_id,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is not None:
                skipped += 1
                await progress.increment()
                continue

            # Create track stub (metadata will be filled by YM sync later)
            track = Track(
                title=f"YM:{ym_id}",
                status=0,
            )
            track = await track_repo.create(track)
            await session.flush()

            # Create external ID link
            ext_id = TrackExternalId(
                track_id=track.id,
                platform="yandex_music",
                external_id=ym_id,
            )
            session.add(ext_id)
            imported += 1
            imported_ids.append(track.id)

            if idx % 10 == 0:
                await progress.set_message(f"Imported {imported} / {len(track_refs)} tracks...")
            await progress.increment()

        await session.commit()

        await progress.set_message(f"Import complete: {imported} new, {skipped} skipped")

        result_dict: dict[str, Any] = {
            "imported": imported,
            "skipped": skipped,
            "total_refs": len(track_refs),
        }
        if errors:
            result_dict["errors"] = errors
        if playlist_id:
            result_dict["playlist_id"] = playlist_id
            result_dict["playlist_note"] = (
                "Playlist assignment requires separate manage_playlist call"
            )

        # Schedule background analysis if requested and we imported tracks
        if auto_analyze and imported_ids:
            from app.mcp.tools.audio import analyze_batch

            await docket.add(
                analyze_batch,
                track_ids=imported_ids,
                analyzers=None,
                priority="normal",
            )
            result_dict["auto_analyze_scheduled"] = True
            result_dict["analysis_track_count"] = len(imported_ids)
            result_dict["note"] = (
                f"Scheduled background analysis for {len(imported_ids)} imported tracks"
            )

        return result_dict


# ── 3. download_tracks ──────────────────────────────


@mcp.tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
    timeout=300.0,
)
async def download_tracks(
    track_refs: list[str],
    target_dir: str | None = None,
    skip_existing: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Download MP3 from YM for given track refs."""
    if not track_refs:
        return {"error": "track_refs is required (list of YM track IDs)"}

    # Stub: actual download requires ym_client with authenticated session
    if ctx:
        await ctx.info(
            f"Download requested for {len(track_refs)} tracks — YM download integration pending"
        )

    return {
        "requested": len(track_refs),
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
        "target_dir": target_dir or "~/Music/DJ/",
        "message": "YM download requires authenticated ym_client — not yet implemented",
    }
