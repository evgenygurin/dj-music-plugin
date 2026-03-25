"""Discovery & download tools (3 tools, tag: discovery)."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_context
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.track import Track, TrackExternalId
from app.repositories.track import TrackRepository
from app.server import mcp

# ── Helpers ──────────────────────────────────────────


async def _get_session() -> AsyncSession:
    """Get async session from lifespan context."""
    ctx = get_context()
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
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    """Find similar tracks by strategy: ym, embedding, llm, combined."""
    valid_strategies = {"ym", "embedding", "llm", "combined"}
    if strategy not in valid_strategies:
        return {
            "error": f"Unknown strategy: {strategy}. Valid: {', '.join(sorted(valid_strategies))}"
        }

    async with await _get_session() as session:
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
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    """Import YM track IDs into local DB. Idempotent — skips existing."""
    if not track_refs:
        return {"error": "track_refs is required (list of YM track IDs)"}

    async with await _get_session() as session:
        track_repo = TrackRepository(session)

        imported = 0
        skipped = 0
        errors: list[str] = []

        for ref in track_refs:
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

            if ctx and imported % 10 == 0:
                await ctx.info(f"Imported {imported} tracks...")

        await session.commit()

        if ctx:
            await ctx.info(f"Import complete: {imported} new, {skipped} skipped")

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
        if auto_analyze:
            result_dict["auto_analyze_note"] = (
                "Auto-analyze requires analyze_batch — trigger separately"
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
    ctx: Context = CurrentContext(),
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
