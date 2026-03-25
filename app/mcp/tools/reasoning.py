"""DJ-specific reasoning tools: suggest, explain, replace, compare, quick review."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context

from app.core.camelot import camelot_distance, key_code_to_camelot
from app.mcp.dependencies import get_db_session
from app.models.set import SetItem, SetVersion
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.server import mcp


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def suggest_next_track(
    set_id: int,
    after_position: int,
    count: int = 5,
    prefer_mood: str | None = None,
    energy_direction: str = "any",
    ctx: Context | None = None,
) -> dict:
    """Suggest best tracks for a set position, scored against both neighbors."""
    async with get_db_session() as session:
        set_repo = SetRepository(session)
        track_repo = TrackRepository(session)

        latest = await set_repo.get_latest_version(set_id)
        if not latest:
            raise ToolError("No version found")

        from sqlalchemy import select

        stmt = select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if after_position < 0 or after_position >= len(items):
            raise ToolError(f"Position {after_position} out of range (0-{len(items) - 1})")

        current_track = await track_repo.get_by_id(items[after_position].track_id)
        next_track = None
        if after_position + 1 < len(items):
            next_track = await track_repo.get_by_id(items[after_position + 1].track_id)

        return {
            "set_id": set_id,
            "after_position": after_position,
            "current_track": current_track.title if current_track else None,
            "next_track": next_track.title if next_track else None,
            "suggestions": [],
            "note": "Full suggestion engine requires Sub-Project #5 (transition scoring)",
        }


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def explain_transition(
    from_track_id: int,
    to_track_id: int,
    ctx: Context | None = None,
) -> dict:
    """Explain why a transition works or doesn't — 5-component breakdown."""
    async with get_db_session() as session:
        track_repo = TrackRepository(session)
        transition_repo = TransitionRepository(session)

        from_track = await track_repo.get_by_id(from_track_id)
        to_track = await track_repo.get_by_id(to_track_id)

        if not from_track or not to_track:
            raise ToolError("One or both tracks not found")

        score = await transition_repo.get_score(from_track_id, to_track_id)

        # Get audio features for explanation
        from app.repositories.feature import FeatureRepository

        feat_repo = FeatureRepository(session)
        from_feat = await feat_repo.get_features(from_track_id)
        to_feat = await feat_repo.get_features(to_track_id)

        explanation = {
            "from_track": {"id": from_track_id, "title": from_track.title},
            "to_track": {"id": to_track_id, "title": to_track.title},
            "has_score": score is not None,
        }

        if from_feat and to_feat:
            bpm_delta = abs((from_feat.bpm or 0) - (to_feat.bpm or 0))
            key_dist = None
            if from_feat.key_code is not None and to_feat.key_code is not None:
                key_dist = camelot_distance(from_feat.key_code, to_feat.key_code)

            explanation["analysis"] = {
                "bpm": {
                    "from": from_feat.bpm,
                    "to": to_feat.bpm,
                    "delta": round(bpm_delta, 1),
                    "note": "Good"
                    if bpm_delta <= 3
                    else ("Acceptable" if bpm_delta <= 6 else "Large jump"),
                },
                "key": {
                    "from": key_code_to_camelot(from_feat.key_code)
                    if from_feat.key_code is not None
                    else None,
                    "to": key_code_to_camelot(to_feat.key_code)
                    if to_feat.key_code is not None
                    else None,
                    "distance": key_dist,
                    "note": (
                        "Compatible"
                        if key_dist is not None and key_dist <= 1
                        else "Acceptable"
                        if key_dist is not None and key_dist <= 2
                        else "Clash"
                        if key_dist is not None
                        else "Unknown"
                    ),
                },
                "energy": {
                    "from_lufs": from_feat.integrated_lufs,
                    "to_lufs": to_feat.integrated_lufs,
                    "delta": round(
                        (to_feat.integrated_lufs or 0) - (from_feat.integrated_lufs or 0), 1
                    ),
                },
            }
        else:
            explanation["analysis"] = None
            explanation["note"] = "Audio features not available for one or both tracks"

        if score:
            explanation["scores"] = {
                "overall": score.overall_quality,
                "bpm": score.bpm_score,
                "harmonic": score.harmonic_score,
                "energy": score.energy_score,
                "spectral": score.spectral_score,
                "groove": score.groove_score,
            }

        return explanation


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def find_replacement(
    set_id: int,
    position: int,
    count: int = 5,
    ctx: Context | None = None,
) -> dict:
    """Find replacement tracks for a set position, scored against both neighbors."""
    # Stub — full implementation in Sub-Project #5
    return {
        "set_id": set_id,
        "position": position,
        "candidates": [],
        "note": "Full replacement engine requires Sub-Project #5 (transition scoring)",
    }


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def compare_set_versions(
    set_id: int,
    version_a: int | None = None,
    version_b: int | None = None,
    ctx: Context | None = None,
) -> dict:
    """Compare two versions of a set: tracks added/removed, score changes."""
    async with get_db_session() as session:
        SetRepository(session)

        from sqlalchemy import select

        # Get versions
        if version_a is None or version_b is None:
            stmt = (
                select(SetVersion)
                .where(SetVersion.set_id == set_id)
                .order_by(SetVersion.id.desc())
                .limit(2)
            )
            result = await session.execute(stmt)
            versions = list(result.scalars().all())
            if len(versions) < 2:
                raise ToolError("Need at least 2 versions to compare")
            ver_b, ver_a = versions[0], versions[1]
        else:
            ver_a = await session.get(SetVersion, version_a)
            ver_b = await session.get(SetVersion, version_b)

        if not ver_a or not ver_b:
            raise ToolError("Version not found")

        # Get track sets
        stmt_a = select(SetItem.track_id).where(SetItem.version_id == ver_a.id)
        stmt_b = select(SetItem.track_id).where(SetItem.version_id == ver_b.id)
        tracks_a = set((await session.execute(stmt_a)).scalars().all())
        tracks_b = set((await session.execute(stmt_b)).scalars().all())

        return {
            "set_id": set_id,
            "version_a": {"id": ver_a.id, "label": ver_a.label, "score": ver_a.quality_score},
            "version_b": {"id": ver_b.id, "label": ver_b.label, "score": ver_b.quality_score},
            "tracks_added": list(tracks_b - tracks_a),
            "tracks_removed": list(tracks_a - tracks_b),
            "tracks_unchanged": len(tracks_a & tracks_b),
            "score_delta": (
                (ver_b.quality_score or 0) - (ver_a.quality_score or 0)
                if ver_a.quality_score is not None and ver_b.quality_score is not None
                else None
            ),
        }


@mcp.tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def quick_set_review(
    set_id: int,
    ctx: Context | None = None,
) -> dict:
    """Complete set review in one call: tracks, weak transitions, problems."""
    async with get_db_session() as session:
        set_repo = SetRepository(session)
        track_repo = TrackRepository(session)

        dj_set = await set_repo.get_by_id(set_id)
        if not dj_set:
            raise ToolError(f"Set {set_id} not found")

        latest = await set_repo.get_latest_version(set_id)
        if not latest:
            raise ToolError("No version found")

        from sqlalchemy import select

        stmt = select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        tracks_summary = []
        for item in items:
            track = await track_repo.get_by_id(item.track_id)
            if track:
                tracks_summary.append(
                    {
                        "pos": item.sort_index,
                        "title": track.title,
                        "pinned": item.pinned,
                    }
                )

        return {
            "set_name": dj_set.name,
            "version": latest.label,
            "quality_score": latest.quality_score,
            "track_count": len(items),
            "template": dj_set.template_name,
            "tracks": tracks_summary,
            "weak_transitions": [],
            "problems": [],
            "note": "Full scoring requires Sub-Project #5",
        }
