"""Set building tools: build, rebuild, score transitions, cheat sheet."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select

from app.mcp.dependencies import get_feature_repo, get_set_repo, get_track_repo, get_transition_repo
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
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict:
    """Build optimized DJ set from playlist. Supports greedy or GA algorithm."""
    if ctx:
        await ctx.info(f"Building set '{name}' from playlist {playlist_id}...")
        await ctx.report_progress(0, 3)

    session = set_repo.session

    # Get tracks from playlist
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
    features_map = await feat_repo.get_scoring_features_batch(track_ids)
    track_features_list = [features_map.get(tid, TrackFeatures()) for tid in track_ids]

    if ctx:
        await ctx.report_progress(2, 4)

    # Optimize track order
    optimized_order, quality, used_algorithm = _optimize_order(
        track_ids, track_features_list, algorithm, ctx,
    )

    if ctx:
        await ctx.report_progress(3, 4)

    if dry_run:
        return {
            "dry_run": True,
            "track_count": len(optimized_order),
            "algorithm": used_algorithm,
            "quality_score": round(quality, 4) if quality else None,
            "has_features": quality is not None,
            "template": template,
        }

    # Persist set + version + items
    dj_set, version = await _create_set_with_version(
        session, name, template, target_duration_min, playlist_id,
        optimized_order, used_algorithm,
    )

    if ctx:
        await ctx.info(f"Set created: {dj_set.id}, version: {version.id}")
        await ctx.report_progress(4, 4)

    return {
        "set_id": dj_set.id,
        "version_id": version.id,
        "track_count": len(optimized_order),
        "algorithm": used_algorithm,
        "quality_score": round(quality, 4) if quality else None,
        "has_features": quality is not None,
    }


def _optimize_order(
    track_ids: list[int],
    track_features_list: list[TrackFeatures],
    algorithm: str,
    ctx: Context | None,
) -> tuple[list[int], float | None, str]:
    """Run optimizer and return (ordered_ids, quality_score, algorithm_used)."""
    from app.services.optimizer import GeneticAlgorithm, GreedyChainBuilder

    scorer = TransitionScorer()
    has_features = any(f.bpm is not None for f in track_features_list)

    if not has_features:
        return track_ids, None, "playlist_order"

    if algorithm in ("ga", "genetic"):
        ga = GeneticAlgorithm(scorer)
        opt_result = ga.optimize(track_features_list, track_ids)
    else:
        builder = GreedyChainBuilder(scorer)
        opt_result = builder.build(track_features_list, track_ids)

    return opt_result.track_order, opt_result.quality_score, algorithm


async def _create_set_with_version(
    session,
    name: str,
    template: str | None,
    target_duration_min: int | None,
    playlist_id: int,
    optimized_order: list[int],
    algorithm: str,
) -> tuple[DjSet, SetVersion]:
    """Create DjSet + first SetVersion + SetItems. Returns (set, version)."""
    import json as _json

    from app.utils.time import utc_timestamp_iso

    dj_set = DjSet(
        name=name,
        target_duration_ms=(target_duration_min * 60_000) if target_duration_min else None,
        template_name=template,
        source_playlist_id=playlist_id,
    )
    session.add(dj_set)
    await session.flush()

    gen_meta = _json.dumps(
        {
            "algorithm": algorithm,
            "playlist_id": playlist_id,
            "track_count": len(optimized_order),
            "template": template,
            "target_duration_min": target_duration_min,
            "timestamp": utc_timestamp_iso(),
        }
    )
    version = SetVersion(
        set_id=dj_set.id,
        label="v1",
        generator_run_meta=gen_meta,
    )
    session.add(version)
    await session.flush()

    for idx, tid in enumerate(optimized_order):
        session.add(SetItem(version_id=version.id, track_id=tid, sort_index=idx))
    await session.flush()

    return dj_set, version


@tool(tags={"sets"}, annotations={"readOnlyHint": False}, timeout=120.0)
async def rebuild_set(
    set_id: int,
    pin_tracks: list[int] | None = None,
    exclude_tracks: list[int] | None = None,
    algorithm: str = "greedy",
    version_label: str | None = None,
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict:
    """Rebuild existing set with pinned/excluded tracks. Creates new version."""
    if ctx:
        await ctx.info(f"Rebuilding set {set_id}...")

    session = set_repo.session

    dj_set = await set_repo.get_by_id(set_id)
    if dj_set is None:
        raise ToolError(f"Set {set_id} not found")

    latest = await set_repo.get_latest_version(set_id)
    if latest is None:
        raise ToolError("No version found for this set")

    # Get current track ids from latest version
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
        session.add(
            SetItem(
                version_id=version.id,
                track_id=tid,
                sort_index=idx,
                pinned=tid in (pin_tracks or []),
            )
        )
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
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    transition_repo: TransitionRepository = Depends(get_transition_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict:
    """Score transitions: mode=set (all pairs), pair (two tracks), track_candidates (best next).

    Computes scores via TransitionScorer and SAVES to DB.
    """
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
        return await _score_set_transitions(set_repo, feat_repo, transition_repo, set_id, ctx)

    raise ToolError("Invalid mode or missing parameters")


async def _compute_and_save(
    feat_repo: FeatureRepository,
    transition_repo: TransitionRepository,
    from_id: int,
    to_id: int,
) -> dict:
    """Compute transition score, save to DB, return dict."""
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


async def _score_set_transitions(
    set_repo: SetRepository,
    feat_repo: FeatureRepository,
    transition_repo: TransitionRepository,
    set_id: int,
    ctx: Context | None,
) -> dict:
    """Score all sequential transitions in a set."""
    latest = await set_repo.get_latest_version(set_id)
    if not latest:
        raise ToolError("No version found")

    stmt = (
        select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
    )
    result = await set_repo.session.execute(stmt)
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


@tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def get_set_cheat_sheet(
    set_id: int,
    version: str | None = None,
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    ctx: Context | None = None,
) -> str:
    """Human-readable cheat sheet: BPM flow, key changes, energy arc."""
    dj_set = await set_repo.get_by_id(set_id)
    if not dj_set:
        raise ToolError(f"Set {set_id} not found")

    latest = await set_repo.get_latest_version(set_id)
    if not latest:
        raise ToolError("No version found")

    stmt = select(SetItem).where(SetItem.version_id == latest.id).order_by(SetItem.sort_index)
    result = await set_repo.session.execute(stmt)
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
            line = f"{i:2d}. {track.title}"
            if item.pinned:
                line += " [PINNED]"
            lines.append(line)

    return "\n".join(lines)

