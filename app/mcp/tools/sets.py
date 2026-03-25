"""Set building tools: build, rebuild, score transitions, cheat sheet."""

from __future__ import annotations

from fastmcp.server.context import Context

from app.models.set import DjSet, SetItem, SetVersion
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.server import mcp


async def _get_session(ctx: Context | None):  # type: ignore[no-untyped-def]
    """Get async session from lifespan context."""
    if ctx is None:
        raise RuntimeError("Context required")
    factory = ctx.lifespan_context["db_session_factory"]
    return factory()


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": False}, timeout=120.0)
async def build_set(
    playlist_id: int,
    name: str,
    template: str | None = None,
    target_duration_min: int | None = None,
    algorithm: str = "greedy",
    dry_run: bool = False,
    ctx: Context | None = None,
) -> dict:
    """Build optimized DJ set from playlist. Supports greedy or GA algorithm."""
    if ctx:
        await ctx.info(f"Building set '{name}' from playlist {playlist_id}...")
        await ctx.report_progress(0, 100)

    async with await _get_session(ctx) as session:
        TrackRepository(session)
        SetRepository(session)

        # Get tracks from playlist
        from sqlalchemy import select

        from app.models.playlist import PlaylistItem

        stmt = (
            select(PlaylistItem.track_id)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.sort_index)
        )
        result = await session.execute(stmt)
        track_ids = [r[0] for r in result.all()]

        if not track_ids:
            return {"error": "Playlist is empty", "set_id": None}

        if ctx:
            await ctx.info(f"Found {len(track_ids)} tracks, building order...")
            await ctx.report_progress(25, 100)

        # For now: use playlist order as-is (GA/greedy will be in Sub-Project #6)
        if ctx:
            await ctx.report_progress(50, 100)

        # Create set and version
        if not dry_run:
            dj_set = DjSet(
                name=name,
                target_duration_ms=(target_duration_min * 60_000) if target_duration_min else None,
                template_name=template,
                source_playlist_id=playlist_id,
            )
            session.add(dj_set)
            await session.flush()

            version = SetVersion(set_id=dj_set.id, label="v1")
            session.add(version)
            await session.flush()

            for idx, tid in enumerate(track_ids):
                item = SetItem(
                    version_id=version.id,
                    track_id=tid,
                    sort_index=idx,
                )
                session.add(item)
            await session.flush()

            if ctx:
                await ctx.info(f"Set created: {dj_set.id}, version: {version.id}")
                await ctx.report_progress(100, 100)

            await session.commit()
            return {
                "set_id": dj_set.id,
                "version_id": version.id,
                "track_count": len(track_ids),
                "algorithm": algorithm,
                "quality_score": None,  # scoring in Sub-Project #5
            }
        else:
            return {
                "dry_run": True,
                "track_count": len(track_ids),
                "algorithm": algorithm,
                "template": template,
            }


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": False}, timeout=120.0)
async def rebuild_set(
    set_id: int,
    pin_tracks: list[int] | None = None,
    exclude_tracks: list[int] | None = None,
    algorithm: str = "greedy",
    version_label: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Rebuild existing set with pinned/excluded tracks. Creates new version."""
    if ctx:
        await ctx.info(f"Rebuilding set {set_id}...")
        await ctx.report_progress(0, 100)

    async with await _get_session(ctx) as session:
        set_repo = SetRepository(session)
        dj_set = await set_repo.get_by_id(set_id)
        if dj_set is None:
            return {"error": f"Set {set_id} not found"}

        latest = await set_repo.get_latest_version(set_id)
        if latest is None:
            return {"error": "No version found for this set"}

        # Get current track ids from latest version
        from sqlalchemy import select

        stmt = (
            select(SetItem.track_id)
            .where(SetItem.version_id == latest.id)
            .order_by(SetItem.sort_index)
        )
        result = await session.execute(stmt)
        current_ids = [r[0] for r in result.all()]

        # Apply pin/exclude
        if ctx:
            await ctx.report_progress(40, 100)
        exclude_set = set(exclude_tracks or [])
        filtered = [tid for tid in current_ids if tid not in exclude_set]

        # Create new version
        label = version_label or f"v{latest.id + 1}"
        version = SetVersion(set_id=set_id, label=label)
        session.add(version)
        await session.flush()

        for idx, tid in enumerate(filtered):
            item = SetItem(
                version_id=version.id,
                track_id=tid,
                sort_index=idx,
                pinned=tid in (pin_tracks or []),
            )
            session.add(item)
        await session.flush()
        if ctx:
            await ctx.report_progress(100, 100)
        await session.commit()

        return {
            "set_id": set_id,
            "version_id": version.id,
            "version_label": label,
            "track_count": len(filtered),
            "excluded": len(exclude_set),
            "pinned": len(pin_tracks or []),
        }


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def score_transitions(
    mode: str = "set",
    set_id: int | None = None,
    from_track_id: int | None = None,
    to_track_id: int | None = None,
    track_id: int | None = None,
    top_n: int = 10,
    ctx: Context | None = None,
) -> dict:
    """Score transitions: mode=set (all pairs), pair (two tracks), track_candidates (best next)."""
    async with await _get_session(ctx) as session:
        transition_repo = TransitionRepository(session)
        TrackRepository(session)

        if mode == "pair" and from_track_id and to_track_id:
            score = await transition_repo.get_score(from_track_id, to_track_id)
            if score:
                return {
                    "from_track_id": from_track_id,
                    "to_track_id": to_track_id,
                    "overall_quality": score.overall_quality,
                    "bpm_score": score.bpm_score,
                    "harmonic_score": score.harmonic_score,
                    "energy_score": score.energy_score,
                    "spectral_score": score.spectral_score,
                    "groove_score": score.groove_score,
                }
            return {
                "from_track_id": from_track_id,
                "to_track_id": to_track_id,
                "overall_quality": None,
                "message": "No transition scored yet",
            }

        elif mode == "track_candidates" and track_id:
            candidates = await transition_repo.get_candidates(track_id, limit=top_n)
            return {
                "track_id": track_id,
                "candidates": [
                    {
                        "to_track_id": c.to_track_id,
                        "bpm_distance": c.bpm_distance,
                        "key_distance": c.key_distance,
                        "embedding_similarity": c.embedding_similarity,
                        "fully_scored": c.fully_scored,
                    }
                    for c in candidates
                ],
            }

        elif mode == "set" and set_id:
            # Get set items in order
            set_repo = SetRepository(session)
            latest = await set_repo.get_latest_version(set_id)
            if not latest:
                return {"error": "No version found"}

            from sqlalchemy import select

            stmt = (
                select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
            )
            result = await session.execute(stmt)
            items = list(result.scalars().all())

            transitions_data = []
            for i in range(len(items) - 1):
                score = await transition_repo.get_score(items[i].track_id, items[i + 1].track_id)
                transitions_data.append(
                    {
                        "position": i,
                        "from_track_id": items[i].track_id,
                        "to_track_id": items[i + 1].track_id,
                        "overall_quality": score.overall_quality if score else None,
                    }
                )

            scored = [t for t in transitions_data if t["overall_quality"] is not None]
            return {
                "set_id": set_id,
                "version_id": latest.id,
                "total_transitions": len(transitions_data),
                "scored_transitions": len(scored),
                "avg_score": (
                    sum(t["overall_quality"] for t in scored) / len(scored) if scored else None
                ),
                "transitions": transitions_data,
            }

        return {"error": "Invalid mode or missing parameters"}


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def get_set_cheat_sheet(
    set_id: int,
    version: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Human-readable cheat sheet: BPM flow, key changes, energy arc."""
    async with await _get_session(ctx) as session:
        set_repo = SetRepository(session)
        track_repo = TrackRepository(session)

        dj_set = await set_repo.get_by_id(set_id)
        if not dj_set:
            return f"Set {set_id} not found"

        latest = await set_repo.get_latest_version(set_id)
        if not latest:
            return "No version found"

        from sqlalchemy import select

        stmt = select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        lines = [
            f"=== {dj_set.name} ===",
            f"Version: {latest.label or latest.id}",
            f"Tracks: {len(items)}",
            f"Score: {latest.quality_score or 'N/A'}",
            "",
        ]

        for i, item in enumerate(items, 1):
            track = await track_repo.get_by_id(item.track_id)
            if track:
                lines.append(f"{i:2d}. {track.title}")
                if item.pinned:
                    lines[-1] += " [PINNED]"

        return "\n".join(lines)
