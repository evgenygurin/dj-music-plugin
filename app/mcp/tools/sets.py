"""Set building tools: build, rebuild, score transitions, cheat sheet."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select

from app.mcp.dependencies import get_db_session
from app.models.set import DjSet, SetItem, SetVersion
from app.models.transition import Transition
from app.repositories.feature import FeatureRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.transition import TrackFeatures, TransitionScorer


@tool(tags={"sets"}, annotations={"readOnlyHint": False}, timeout=120.0)
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
        await ctx.report_progress(0, 3)

    async with get_db_session() as session:
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
            raise ToolError("Playlist is empty")

        if ctx:
            await ctx.info(f"Found {len(track_ids)} tracks, loading features...")
            await ctx.report_progress(1, 4)

        # Load audio features for optimization (batch: 1 SQL instead of N)
        feat_repo = FeatureRepository(session)
        features_map = await feat_repo.get_scoring_features_batch(track_ids)
        track_features_list = [features_map.get(tid, TrackFeatures()) for tid in track_ids]

        if ctx:
            await ctx.report_progress(2, 4)

        # Optimize track order
        from app.services.optimizer import GeneticAlgorithm, GreedyChainBuilder

        scorer = TransitionScorer()
        has_features = any(f.bpm is not None for f in track_features_list)

        if has_features and algorithm == "greedy":
            if ctx:
                await ctx.info("Optimizing with greedy chain builder...")
            builder = GreedyChainBuilder(scorer)
            opt_result = builder.build(track_features_list, track_ids)
            optimized_order = opt_result.track_order
            quality = opt_result.quality_score
        elif has_features and algorithm in ("ga", "genetic"):
            if ctx:
                await ctx.info("Optimizing with genetic algorithm...")
            ga = GeneticAlgorithm(scorer)
            opt_result = ga.optimize(track_features_list, track_ids)
            optimized_order = opt_result.track_order
            quality = opt_result.quality_score
        else:
            # No features — use playlist order as fallback
            if ctx and not has_features:
                await ctx.info(
                    "No audio features — using playlist order (analyze tracks for optimization)"
                )
            optimized_order = track_ids
            quality = None

        if ctx:
            await ctx.report_progress(3, 4)

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

            for idx, tid in enumerate(optimized_order):
                item = SetItem(
                    version_id=version.id,
                    track_id=tid,
                    sort_index=idx,
                )
                session.add(item)
            await session.flush()

            if ctx:
                await ctx.info(f"Set created: {dj_set.id}, version: {version.id}")
                await ctx.report_progress(4, 4)

            return {
                "set_id": dj_set.id,
                "version_id": version.id,
                "track_count": len(optimized_order),
                "algorithm": algorithm if has_features else "playlist_order",
                "quality_score": round(quality, 4) if quality else None,
                "has_features": has_features,
            }
        else:
            return {
                "dry_run": True,
                "track_count": len(optimized_order),
                "algorithm": algorithm if has_features else "playlist_order",
                "quality_score": round(quality, 4) if quality else None,
                "has_features": has_features,
                "template": template,
            }


@tool(tags={"sets"}, annotations={"readOnlyHint": False}, timeout=120.0)
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

    async with get_db_session() as session:
        set_repo = SetRepository(session)
        dj_set = await set_repo.get_by_id(set_id)
        if dj_set is None:
            raise ToolError(f"Set {set_id} not found")

        latest = await set_repo.get_latest_version(set_id)
        if latest is None:
            raise ToolError("No version found for this set")

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

        return {
            "set_id": set_id,
            "version_id": version.id,
            "version_label": label,
            "track_count": len(filtered),
            "excluded": len(exclude_set),
            "pinned": len(pin_tracks or []),
        }


@tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def score_transitions(
    mode: str = "set",
    set_id: int | None = None,
    from_track_id: int | None = None,
    to_track_id: int | None = None,
    track_id: int | None = None,
    top_n: int = 10,
    ctx: Context | None = None,
) -> dict:
    """Score transitions: mode=set (all pairs), pair (two tracks), track_candidates (best next).

    Computes scores via TransitionScorer and SAVES to DB.
    """

    async def _compute_and_save(feat_repo, transition_repo, from_id: int, to_id: int) -> dict:
        """Compute transition score, save to DB, return dict."""
        # Check cached
        existing = await transition_repo.get_score(from_id, to_id)
        if existing and existing.overall_quality is not None:
            return {
                "from_track_id": from_id,
                "to_track_id": to_id,
                "overall_quality": existing.overall_quality,
                "bpm_score": existing.bpm_score,
                "harmonic_score": existing.harmonic_score,
                "energy_score": existing.energy_score,
                "spectral_score": existing.spectral_score,
                "groove_score": existing.groove_score,
                "cached": True,
            }

        ft_from = await feat_repo.get_scoring_features(from_id)
        ft_to = await feat_repo.get_scoring_features(to_id)

        if not ft_from or not ft_to:
            return {
                "from_track_id": from_id,
                "to_track_id": to_id,
                "overall_quality": None,
                "message": "Missing audio features for one or both tracks",
            }

        scorer = TransitionScorer()
        score = scorer.score(ft_from, ft_to)

        # Save to DB
        transition = Transition(
            from_track_id=from_id,
            to_track_id=to_id,
            overall_quality=score.overall if not score.hard_reject else 0.0,
            bpm_score=score.bpm,
            harmonic_score=score.harmonic,
            energy_score=score.energy,
            spectral_score=score.spectral,
            groove_score=score.groove,
        )
        await transition_repo.save_score(transition)

        return {
            "from_track_id": from_id,
            "to_track_id": to_id,
            "overall_quality": round(score.overall, 4) if not score.hard_reject else 0.0,
            "bpm_score": round(score.bpm, 4),
            "harmonic_score": round(score.harmonic, 4),
            "energy_score": round(score.energy, 4),
            "spectral_score": round(score.spectral, 4),
            "groove_score": round(score.groove, 4),
            "hard_reject": score.hard_reject,
            "reject_reason": score.reject_reason,
            "cached": False,
        }

    async with get_db_session() as session:
        transition_repo = TransitionRepository(session)
        feat_repo = FeatureRepository(session)

        if mode == "pair" and from_track_id and to_track_id:
            return await _compute_and_save(feat_repo, transition_repo, from_track_id, to_track_id)

        if mode == "track_candidates" and track_id:
            candidates = await transition_repo.get_candidates(track_id, limit=top_n)
            return {
                "track_id": track_id,
                "candidates": [
                    {
                        "to_track_id": c.to_track_id,
                        "bpm_distance": c.bpm_distance,
                        "key_distance": c.key_distance,
                        "fully_scored": c.fully_scored,
                    }
                    for c in candidates
                ],
            }

        if mode == "set" and set_id:
            set_repo = SetRepository(session)
            latest = await set_repo.get_latest_version(set_id)
            if not latest:
                raise ToolError("No version found")

            stmt = (
                select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
            )
            result = await session.execute(stmt)
            items = list(result.scalars().all())

            if ctx:
                await ctx.info(f"Scoring {len(items) - 1} transitions...")

            transitions_data = []
            for i in range(len(items) - 1):
                score_data = await _compute_and_save(
                    feat_repo, transition_repo, items[i].track_id, items[i + 1].track_id
                )
                score_data["position"] = i
                transitions_data.append(score_data)
                if ctx:
                    await ctx.report_progress(i + 1, len(items) - 1)

            scored = [t for t in transitions_data if t.get("overall_quality") is not None]
            hard_conflicts = [t for t in scored if t.get("overall_quality") == 0.0]

            return {
                "set_id": set_id,
                "version_id": latest.id,
                "total_transitions": len(transitions_data),
                "scored_transitions": len(scored),
                "hard_conflicts": len(hard_conflicts),
                "avg_score": (
                    sum(t["overall_quality"] for t in scored if t["overall_quality"])
                    / max(1, len(scored) - len(hard_conflicts))
                    if scored
                    else None
                ),
                "transitions": transitions_data,
            }

        raise ToolError("Invalid mode or missing parameters")


@tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def get_set_cheat_sheet(
    set_id: int,
    version: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Human-readable cheat sheet: BPM flow, key changes, energy arc."""
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
