"""Curation tools (5 tools, tag: curation).

Tools:
- classify_mood: classify tracks by 15 techno subgenres
- audit_playlist: audit playlist for quality criteria
- quick_set_review: review set transitions quality
- distribute_to_subgenres: sort tracks into subgenre playlists
- get_library_stats: library dashboard stats
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audio.mood import MoodClassifier
from app.config import settings
from app.core.constants import TechnoSubgenre
from app.mcp.dependencies import (
    get_db_session,
    get_feature_repo,
    get_playlist_repo,
    get_set_repo,
    get_track_repo,
    get_transition_repo,
)
from app.models.audio import TrackAudioFeaturesComputed
from app.models.playlist import Playlist, PlaylistItem
from app.models.set import DjSet, SetItem, SetVersion
from app.models.track import Track
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository


# ── 1. classify_mood ─────────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": True})
async def classify_mood(
    track_ids: Any = None,
    playlist_id: int | None = None,
    reclassify: bool = False,
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Classify tracks by 15 techno subgenres using rule-based MoodClassifier."""
    from app.core.parsing import ensure_list

    track_ids = ensure_list(track_ids) or None
    if not track_ids and playlist_id is None:
        raise ToolError("Provide track_ids or playlist_id")

    ids_to_classify: list[int] = list(track_ids or [])
    if playlist_id is not None:
        stmt = (
            select(PlaylistItem.track_id)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.sort_index)
        )
        result = await session.execute(stmt)
        ids_to_classify.extend(r[0] for r in result.all())

    if not ids_to_classify:
        raise ToolError("No tracks to classify")

    classifier = MoodClassifier()
    classifications: list[dict[str, Any]] = []
    skipped = 0

    for i, tid in enumerate(ids_to_classify):
        features = await feat_repo.get_features(tid)
        if features is None:
            skipped += 1
            continue

        # DRY: use model method instead of manual 27-field mapping
        feat_dict = features.to_classifier_dict()
        mood_result = classifier.classify(feat_dict)

        classifications.append({
            "track_id": tid,
            "mood": mood_result.mood.value,
            "confidence": round(mood_result.confidence, 3),
            "reasoning": mood_result.reasoning,
            "top_3": [
                {"subgenre": sg.value, "score": round(sc, 3)}
                for sg, sc in sorted(
                    mood_result.scores.items(), key=lambda x: x[1], reverse=True
                )[:3]
            ],
        })

        if ctx and (i + 1) % 20 == 0:
            await ctx.info(f"Classified {i + 1}/{len(ids_to_classify)} tracks")

    mood_counts: dict[str, int] = {}
    for c in classifications:
        mood = c["mood"]
        mood_counts[mood] = mood_counts.get(mood, 0) + 1

    return {
        "classified": len(classifications),
        "skipped_no_features": skipped,
        "total": len(ids_to_classify),
        "distribution": mood_counts,
        "tracks": classifications,
    }


# ── 2. audit_playlist ───────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": True})
async def audit_playlist(
    playlist_id: int | None = None,
    playlist_query: str | None = None,
    check: str | None = None,
    template: str | None = None,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    track_repo: TrackRepository = Depends(get_track_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Audit playlist for techno quality criteria and library gaps."""
    if playlist_id is None and playlist_query is None:
        raise ToolError("Provide playlist_id or playlist_query")

    playlist: Playlist | None = None
    if playlist_id is not None:
        stmt = (
            select(Playlist)
            .where(Playlist.id == playlist_id)
            .options(selectinload(Playlist.items))
        )
        result = await session.execute(stmt)
        playlist = result.scalar_one_or_none()
    elif playlist_query:
        stmt = (
            select(Playlist)
            .where(Playlist.name.ilike(f"%{playlist_query}%"))
            .options(selectinload(Playlist.items))
            .limit(1)
        )
        result = await session.execute(stmt)
        playlist = result.scalar_one_or_none()

    if playlist is None:
        raise ToolError("Playlist not found")

    track_ids = [item.track_id for item in sorted(playlist.items, key=lambda i: i.sort_index)]
    if not track_ids:
        raise ToolError("Playlist is empty")

    issues: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "total_tracks": len(track_ids),
        "with_features": 0,
        "without_features": 0,
    }
    bpm_values: list[float] = []
    energy_values: list[float] = []

    for tid in track_ids:
        track = await track_repo.get_by_id(tid)
        if track is None:
            issues.append({"track_id": tid, "issue": "track_missing", "severity": "error"})
            continue

        features = await feat_repo.get_features(tid)
        if features is None:
            stats["without_features"] += 1
            issues.append({
                "track_id": tid,
                "title": track.title,
                "issue": "no_audio_features",
                "severity": "warning",
            })
            continue

        stats["with_features"] += 1

        if features.bpm is not None:
            bpm_values.append(features.bpm)
            if features.bpm < settings.techno_bpm_min or features.bpm > settings.techno_bpm_max:
                issues.append({
                    "track_id": tid,
                    "title": track.title,
                    "issue": "bpm_out_of_range",
                    "severity": "warning",
                    "detail": (
                        f"BPM {features.bpm:.1f} outside "
                        f"[{settings.techno_bpm_min}-{settings.techno_bpm_max}]"
                    ),
                })

        if features.integrated_lufs is not None:
            energy_values.append(features.integrated_lufs)
            if (
                features.integrated_lufs < settings.techno_lufs_min
                or features.integrated_lufs > settings.techno_lufs_max
            ):
                issues.append({
                    "track_id": tid,
                    "title": track.title,
                    "issue": "lufs_out_of_range",
                    "severity": "warning",
                    "detail": (
                        f"LUFS {features.integrated_lufs:.1f} outside "
                        f"[{settings.techno_lufs_min}-{settings.techno_lufs_max}]"
                    ),
                })

    if bpm_values:
        stats["bpm_range"] = [round(min(bpm_values), 1), round(max(bpm_values), 1)]
        stats["bpm_mean"] = round(sum(bpm_values) / len(bpm_values), 1)
    if energy_values:
        stats["lufs_range"] = [round(min(energy_values), 1), round(max(energy_values), 1)]
        stats["lufs_mean"] = round(sum(energy_values) / len(energy_values), 1)

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    return {
        "playlist_id": playlist.id,
        "playlist_name": playlist.name,
        "stats": stats,
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": issues,
    }


# ── 3. quick_set_review ─────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": True})
async def quick_set_review(
    set_id: int,
    version: str | None = None,
    set_repo: SetRepository = Depends(get_set_repo),  # noqa: B008
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    transition_repo: TransitionRepository = Depends(get_transition_repo),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Review set quality: transition scores, BPM flow, energy arc, quality rating."""

    dj_set = await set_repo.get_by_id(set_id)
    if dj_set is None:
        raise ToolError(f"Set {set_id} not found")

    # Get target version
    target_version: SetVersion | None = None
    if version:
        stmt = (
            select(SetVersion)
            .where(SetVersion.set_id == set_id, SetVersion.label == version)
        )
        result = await session.execute(stmt)
        target_version = result.scalar_one_or_none()
    else:
        target_version = await set_repo.get_latest_version(set_id)

    if target_version is None:
        raise ToolError("Version not found")

    # Get items
    stmt = (
        select(SetItem)
        .where(SetItem.version_id == target_version.id)
        .order_by(SetItem.sort_index)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    if not items:
        raise ToolError("Set is empty")

    # Collect BPM/energy flows
    bpm_flow: list[float | None] = []
    energy_flow: list[float | None] = []
    for item in items:
        features = await feat_repo.get_features(item.track_id)
        if features:
            bpm_flow.append(features.bpm)
            energy_flow.append(features.energy_mean)
        else:
            bpm_flow.append(None)
            energy_flow.append(None)

    # Score transitions
    transition_scores: list[float | None] = []
    hard_conflicts = 0
    weak_transitions = 0

    for i in range(len(items) - 1):
        score = await transition_repo.get_score(items[i].track_id, items[i + 1].track_id)
        if score and score.overall_quality is not None:
            transition_scores.append(score.overall_quality)
            if score.overall_quality == 0.0:
                hard_conflicts += 1
            elif score.overall_quality < 0.5:
                weak_transitions += 1
        else:
            transition_scores.append(None)

    scored = [s for s in transition_scores if s is not None]
    avg_score = sum(scored) / len(scored) if scored else None

    # BPM consistency
    valid_bpms = [b for b in bpm_flow if b is not None]
    bpm_jumps = 0
    if len(valid_bpms) > 1:
        for i in range(len(valid_bpms) - 1):
            if abs(valid_bpms[i] - valid_bpms[i + 1]) > settings.transition_hard_reject_bpm_diff:
                bpm_jumps += 1

    # Quality rating
    quality_issues: list[str] = []
    if hard_conflicts > 0:
        quality_issues.append(f"{hard_conflicts} hard conflict(s)")
    if weak_transitions > 2:
        quality_issues.append(f"{weak_transitions} weak transitions")
    if bpm_jumps > 1:
        quality_issues.append(f"{bpm_jumps} large BPM jumps")
    if len(scored) < len(items) - 1:
        quality_issues.append(f"{len(items) - 1 - len(scored)} unscored transitions")

    if not quality_issues:
        rating = "excellent"
    elif len(quality_issues) <= 1:
        rating = "good"
    elif len(quality_issues) <= 3:
        rating = "fair"
    else:
        rating = "poor"

    return {
        "set_id": set_id,
        "set_name": dj_set.name,
        "version": target_version.label,
        "track_count": len(items),
        "rating": rating,
        "avg_transition_score": round(avg_score, 3) if avg_score is not None else None,
        "hard_conflicts": hard_conflicts,
        "weak_transitions": weak_transitions,
        "bpm_jumps": bpm_jumps,
        "unscored_transitions": len(items) - 1 - len(scored),
        "quality_issues": quality_issues,
        "bpm_flow": bpm_flow,
        "energy_flow": energy_flow,
        "transition_scores": transition_scores,
    }


# ── 4. distribute_to_subgenres ──────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": False})
async def distribute_to_subgenres(
    source_playlist_id: int | None = None,
    mode: str = "append",
    sync_to_ym: bool = False,
    dry_run: bool = False,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Distribute tracks to 15 subgenre playlists based on mood classification."""
    valid_modes = {"append", "clean_rebuild"}
    if mode not in valid_modes:
        raise ToolError(f"Unknown mode: {mode}. Valid: {', '.join(sorted(valid_modes))}")

    # Get source tracks
    if source_playlist_id is not None:
        stmt = (
            select(PlaylistItem.track_id)
            .where(PlaylistItem.playlist_id == source_playlist_id)
            .order_by(PlaylistItem.sort_index)
        )
        result = await session.execute(stmt)
        track_ids = [r[0] for r in result.all()]
    else:
        stmt = select(Track.id).where(Track.status == 0)
        result = await session.execute(stmt)
        track_ids = [r[0] for r in result.all()]

    if not track_ids:
        raise ToolError("No tracks to distribute")

    if ctx:
        await ctx.info(f"Distributing {len(track_ids)} tracks to subgenre playlists...")

    classifier = MoodClassifier()
    distribution: dict[str, list[int]] = {sg.value: [] for sg in TechnoSubgenre}
    skipped = 0

    for tid in track_ids:
        features = await feat_repo.get_features(tid)
        if features is None:
            skipped += 1
            continue

        # DRY: use model method instead of manual 27-field mapping
        feat_dict = features.to_classifier_dict()
        mood_result = classifier.classify(feat_dict)
        distribution[mood_result.mood.value].append(tid)

    if dry_run:
        summary = {sg: len(ids) for sg, ids in distribution.items() if ids}
        return {
            "dry_run": True,
            "total_tracks": len(track_ids),
            "classified": len(track_ids) - skipped,
            "skipped_no_features": skipped,
            "distribution": summary,
        }

    # Create/update subgenre playlists
    created_playlists = 0
    total_assigned = 0

    for subgenre in TechnoSubgenre:
        sg_track_ids = distribution[subgenre.value]
        if not sg_track_ids:
            continue

        playlist_name = f"Subgenre: {subgenre.value}"
        stmt_find = select(Playlist).where(Playlist.name == playlist_name).limit(1)
        result = await session.execute(stmt_find)
        playlist = result.scalar_one_or_none()

        if playlist is None:
            playlist = Playlist(name=playlist_name, source_of_truth="local")
            playlist = await playlist_repo.create(playlist)
            await session.flush()
            created_playlists += 1

        if mode == "clean_rebuild":
            stmt_del = select(PlaylistItem).where(PlaylistItem.playlist_id == playlist.id)
            result_del = await session.execute(stmt_del)
            for item in result_del.scalars().all():
                await session.delete(item)
            await session.flush()
            start_idx = 0
        else:
            stmt_max = select(func.max(PlaylistItem.sort_index)).where(
                PlaylistItem.playlist_id == playlist.id
            )
            result_max = await session.execute(stmt_max)
            max_idx = result_max.scalar() or -1
            start_idx = max_idx + 1

        for i, tid in enumerate(sg_track_ids):
            await playlist_repo.add_track(playlist.id, tid, start_idx + i)
            total_assigned += 1

    summary = {sg: len(ids) for sg, ids in distribution.items() if ids}

    return {
        "total_tracks": len(track_ids),
        "classified": len(track_ids) - skipped,
        "skipped_no_features": skipped,
        "created_playlists": created_playlists,
        "total_assigned": total_assigned,
        "distribution": summary,
        "synced_to_ym": False,
    }


# ── 5. get_library_stats ────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": True})
async def get_library_stats(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Library dashboard: counts, coverage, distributions."""
    total_tracks = (await session.execute(select(func.count(Track.id)))).scalar() or 0
    active_tracks = (
        await session.execute(select(func.count(Track.id)).where(Track.status == 0))
    ).scalar() or 0
    archived_tracks = (
        await session.execute(select(func.count(Track.id)).where(Track.status == 1))
    ).scalar() or 0
    tracks_with_features = (
        await session.execute(select(func.count(TrackAudioFeaturesComputed.track_id)))
    ).scalar() or 0
    playlist_count = (await session.execute(select(func.count(Playlist.id)))).scalar() or 0
    set_count = (await session.execute(select(func.count(DjSet.id)))).scalar() or 0

    # BPM distribution
    bpm_ranges: dict[str, int] = {}
    if tracks_with_features > 0:
        stmt_bpm = select(TrackAudioFeaturesComputed.bpm).where(
            TrackAudioFeaturesComputed.bpm.isnot(None)
        )
        result = await session.execute(stmt_bpm)
        for (bpm,) in result.all():
            if bpm is not None:
                bucket = f"{int(bpm // 10) * 10}-{int(bpm // 10) * 10 + 9}"
                bpm_ranges[bucket] = bpm_ranges.get(bucket, 0) + 1

    from app.models.track import TrackExternalId

    ym_linked = (
        await session.execute(
            select(func.count(TrackExternalId.id)).where(
                TrackExternalId.platform == "yandex_music"
            )
        )
    ).scalar() or 0

    return {
        "tracks": {
            "total": total_tracks,
            "active": active_tracks,
            "archived": archived_tracks,
            "with_features": tracks_with_features,
            "without_features": active_tracks - tracks_with_features,
            "feature_coverage": (
                round(tracks_with_features / active_tracks * 100, 1) if active_tracks > 0 else 0.0
            ),
        },
        "playlists": playlist_count,
        "sets": set_count,
        "ym_linked_tracks": ym_linked,
        "bpm_distribution": dict(sorted(bpm_ranges.items())),
    }
