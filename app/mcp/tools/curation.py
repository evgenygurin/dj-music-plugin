"""Curation tools (5 tools, tag: curation)."""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audio.mood import MoodClassifier
from app.config import settings
from app.core.constants import TechnoSubgenre
from app.core.elicitation import safe_confirm
from app.models.audio import TrackAudioFeaturesComputed
from app.models.playlist import Playlist, PlaylistItem
from app.models.set import DjSet, SetItem
from app.models.track import Track
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.server import mcp

# ── Helpers ──────────────────────────────────────────


async def _get_session(ctx: Context | None) -> AsyncSession:
    """Get async session from lifespan context."""
    if ctx is None:
        raise RuntimeError("Context required — tools must be called via MCP")
    factory = ctx.lifespan_context["db_session_factory"]
    return factory()


async def _load_track_features(
    session: AsyncSession, track_id: int
) -> TrackAudioFeaturesComputed | None:
    """Load audio features for a track."""
    stmt = select(TrackAudioFeaturesComputed).where(
        TrackAudioFeaturesComputed.track_id == track_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _features_to_dict(f: TrackAudioFeaturesComputed) -> dict[str, Any]:
    """Convert features model to dict suitable for MoodClassifier."""
    return {
        "energy_mean": f.energy_mean,
        "energy_max": f.energy_max,
        "energy_std": f.energy_std,
        "energy_slope": f.energy_slope,
        "spectral_centroid_hz": f.spectral_centroid_hz,
        "spectral_rolloff_85": f.spectral_rolloff_85,
        "spectral_rolloff_95": f.spectral_rolloff_95,
        "spectral_flatness": f.spectral_flatness,
        "spectral_flux_mean": f.spectral_flux_mean,
        "spectral_contrast": f.spectral_contrast,
        "integrated_lufs": f.integrated_lufs,
        "short_term_lufs_mean": f.short_term_lufs_mean,
        "momentary_max": f.momentary_max,
        "rms_dbfs": f.rms_dbfs,
        "true_peak_db": f.true_peak_db,
        "crest_factor_db": f.crest_factor_db,
        "loudness_range_lu": f.loudness_range_lu,
        "hp_ratio": f.hp_ratio,
        "onset_rate": f.onset_rate,
        "pulse_clarity": f.pulse_clarity,
        "kick_prominence": f.kick_prominence,
        "bpm": f.bpm,
        "bpm_confidence": f.bpm_confidence,
        "bpm_stability": f.bpm_stability,
        "key_code": f.key_code,
        "key_confidence": f.key_confidence,
        "atonality": f.atonality,
        "hnr_db": f.hnr_db,
    }


# ── 1. classify_mood ────────────────────────────────


@mcp.tool(
    tags={"curation"},
    annotations={"readOnlyHint": True},
)
async def classify_mood(
    track_ids: list[int] | None = None,
    playlist_id: int | None = None,
    reclassify: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Classify tracks by 15 techno subgenres using rule-based MoodClassifier."""
    if not track_ids and playlist_id is None:
        return {"error": "Provide track_ids or playlist_id"}

    async with await _get_session(ctx) as session:
        # Resolve track IDs from playlist if needed
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
            return {"error": "No tracks to classify"}

        classifier = MoodClassifier()
        classifications: list[dict[str, Any]] = []
        skipped = 0

        for i, tid in enumerate(ids_to_classify):
            features = await _load_track_features(session, tid)
            if features is None:
                skipped += 1
                continue

            feat_dict = _features_to_dict(features)
            mood_result = classifier.classify(feat_dict)

            classifications.append(
                {
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
                }
            )

            if ctx and (i + 1) % 20 == 0:
                await ctx.info(f"Classified {i + 1}/{len(ids_to_classify)} tracks")

        # Distribution summary
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


@mcp.tool(
    tags={"curation"},
    annotations={"readOnlyHint": True},
)
async def audit_playlist(
    playlist_id: int | None = None,
    playlist_query: str | None = None,
    check: str | None = None,
    template: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Audit playlist for techno quality criteria and library gaps."""
    if playlist_id is None and playlist_query is None:
        return {"error": "Provide playlist_id or playlist_query"}

    async with await _get_session(ctx) as session:
        # Resolve playlist
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
            return {"error": "Playlist not found"}

        track_ids = [item.track_id for item in sorted(playlist.items, key=lambda i: i.sort_index)]
        if not track_ids:
            return {"error": "Playlist is empty"}

        track_repo = TrackRepository(session)

        # Audit checks
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

            features = await _load_track_features(session, tid)
            if features is None:
                stats["without_features"] += 1
                issues.append(
                    {
                        "track_id": tid,
                        "title": track.title,
                        "issue": "no_audio_features",
                        "severity": "warning",
                    }
                )
                continue

            stats["with_features"] += 1

            # BPM check
            if features.bpm is not None:
                bpm_values.append(features.bpm)
                if (
                    features.bpm < settings.techno_bpm_min
                    or features.bpm > settings.techno_bpm_max
                ):
                    issues.append(
                        {
                            "track_id": tid,
                            "title": track.title,
                            "issue": "bpm_out_of_range",
                            "severity": "warning",
                            "detail": (
                                f"BPM {features.bpm:.1f} outside "
                                f"[{settings.techno_bpm_min}-{settings.techno_bpm_max}]"
                            ),
                        }
                    )

            # LUFS check
            if features.integrated_lufs is not None:
                energy_values.append(features.integrated_lufs)
                if (
                    features.integrated_lufs < settings.techno_lufs_min
                    or features.integrated_lufs > settings.techno_lufs_max
                ):
                    issues.append(
                        {
                            "track_id": tid,
                            "title": track.title,
                            "issue": "lufs_out_of_range",
                            "severity": "warning",
                            "detail": (
                                f"LUFS {features.integrated_lufs:.1f} outside "
                                f"[{settings.techno_lufs_min}-{settings.techno_lufs_max}]"
                            ),
                        }
                    )

        # Summary stats
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
            "issues_count": len(issues),
            "errors": len(errors),
            "warnings": len(warnings),
            "issues": issues,
            "verdict": "pass" if not errors and len(warnings) <= 2 else "needs_attention",
        }


# ── 3. review_set_quality ───────────────────────────


@mcp.tool(
    tags={"curation"},
    annotations={"readOnlyHint": True},
)
async def review_set_quality(
    set_id: int,
    version: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Detailed set quality review: transitions, energy arc, key flow."""
    async with await _get_session(ctx) as session:
        set_repo = SetRepository(session)
        TrackRepository(session)
        transition_repo = TransitionRepository(session)

        dj_set = await set_repo.get_by_id(set_id)
        if dj_set is None:
            return {"error": f"Set {set_id} not found"}

        target_version = await set_repo.get_latest_version(set_id)
        if target_version is None:
            return {"error": "No version found"}

        stmt = (
            select(SetItem)
            .where(SetItem.version_id == target_version.id)
            .order_by(SetItem.sort_index)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            return {"error": "Set has no tracks"}

        # Collect per-track data
        bpm_flow: list[float | None] = []
        energy_flow: list[float | None] = []
        key_flow: list[int | None] = []

        for item in items:
            features = await _load_track_features(session, item.track_id)
            if features:
                bpm_flow.append(features.bpm)
                energy_flow.append(features.integrated_lufs)
                key_flow.append(features.key_code)
            else:
                bpm_flow.append(None)
                energy_flow.append(None)
                key_flow.append(None)

        # Transition scores
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
                if (
                    abs(valid_bpms[i] - valid_bpms[i + 1])
                    > settings.transition_hard_reject_bpm_diff
                ):
                    bpm_jumps += 1

        # Overall quality rating
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


@mcp.tool(
    tags={"curation"},
    annotations={"readOnlyHint": False},
)
async def distribute_to_subgenres(
    source_playlist_id: int | None = None,
    mode: str = "append",
    sync_to_ym: bool = False,
    dry_run: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Distribute tracks to 15 subgenre playlists based on mood classification."""
    valid_modes = {"append", "clean_rebuild"}
    if mode not in valid_modes:
        return {"error": f"Unknown mode: {mode}. Valid: {', '.join(sorted(valid_modes))}"}

    async with await _get_session(ctx) as session:
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
            # All active tracks
            stmt = select(Track.id).where(Track.status == 0)
            result = await session.execute(stmt)
            track_ids = [r[0] for r in result.all()]

        if not track_ids:
            return {"error": "No tracks to distribute"}

        if ctx:
            await ctx.info(f"Distributing {len(track_ids)} tracks to subgenre playlists...")

        # ── Elicitation Point: Confirm clean_rebuild ──
        if mode == "clean_rebuild":
            confirmed = await safe_confirm(
                ctx,
                message=(
                    f"⚠️ Mode 'clean_rebuild' will DELETE all existing tracks from subgenre playlists "
                    f"before redistributing {len(track_ids)} tracks. Continue?"
                ),
                default=False,
            )
            if confirmed is None or not confirmed:
                return {
                    "cancelled": True,
                    "reason": "User cancelled clean_rebuild operation",
                    "total_tracks": len(track_ids),
                }

        # Classify all tracks
        classifier = MoodClassifier()
        distribution: dict[str, list[int]] = {sg.value: [] for sg in TechnoSubgenre}
        skipped = 0

        for tid in track_ids:
            features = await _load_track_features(session, tid)
            if features is None:
                skipped += 1
                continue

            feat_dict = _features_to_dict(features)
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
        from app.repositories.playlist import PlaylistRepository

        playlist_repo = PlaylistRepository(session)
        created_playlists = 0
        total_assigned = 0

        for subgenre in TechnoSubgenre:
            sg_track_ids = distribution[subgenre.value]
            if not sg_track_ids:
                continue

            # Find or create playlist
            playlist_name = f"Subgenre: {subgenre.value}"
            stmt_find = select(Playlist).where(Playlist.name == playlist_name).limit(1)
            result = await session.execute(stmt_find)
            playlist = result.scalar_one_or_none()

            if playlist is None:
                playlist = Playlist(name=playlist_name, source_of_truth="local")
                playlist = await playlist_repo.create(playlist)
                await session.flush()
                created_playlists += 1

            # Add tracks
            if mode == "clean_rebuild":
                # Remove existing items
                stmt_del = select(PlaylistItem).where(PlaylistItem.playlist_id == playlist.id)
                result_del = await session.execute(stmt_del)
                for item in result_del.scalars().all():
                    await session.delete(item)
                await session.flush()
                start_idx = 0
            else:
                # Append after existing
                stmt_max = select(func.max(PlaylistItem.sort_index)).where(
                    PlaylistItem.playlist_id == playlist.id
                )
                result_max = await session.execute(stmt_max)
                max_idx = result_max.scalar() or -1
                start_idx = max_idx + 1

            for i, tid in enumerate(sg_track_ids):
                await playlist_repo.add_track(playlist.id, tid, start_idx + i)
                total_assigned += 1

        await session.commit()

        summary = {sg: len(ids) for sg, ids in distribution.items() if ids}

        return {
            "total_tracks": len(track_ids),
            "classified": len(track_ids) - skipped,
            "skipped_no_features": skipped,
            "created_playlists": created_playlists,
            "total_assigned": total_assigned,
            "distribution": summary,
            "synced_to_ym": False,  # YM sync is future
        }


# ── 5. get_library_stats ────────────────────────────


@mcp.tool(
    tags={"curation"},
    annotations={"readOnlyHint": True},
)
async def get_library_stats(
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Library dashboard: counts, coverage, distributions."""
    async with await _get_session(ctx) as session:
        # Track counts
        stmt_total = select(func.count(Track.id))
        result = await session.execute(stmt_total)
        total_tracks = result.scalar() or 0

        stmt_active = select(func.count(Track.id)).where(Track.status == 0)
        result = await session.execute(stmt_active)
        active_tracks = result.scalar() or 0

        stmt_archived = select(func.count(Track.id)).where(Track.status == 1)
        result = await session.execute(stmt_archived)
        archived_tracks = result.scalar() or 0

        # Features coverage
        stmt_features = select(func.count(TrackAudioFeaturesComputed.track_id))
        result = await session.execute(stmt_features)
        tracks_with_features = result.scalar() or 0

        # Playlist count
        stmt_playlists = select(func.count(Playlist.id))
        result = await session.execute(stmt_playlists)
        playlist_count = result.scalar() or 0

        # Set count
        stmt_sets = select(func.count(DjSet.id))
        result = await session.execute(stmt_sets)
        set_count = result.scalar() or 0

        # BPM distribution (if features available)
        bpm_ranges: dict[str, int] = {}
        if tracks_with_features > 0:
            stmt_bpm = select(TrackAudioFeaturesComputed.bpm).where(
                TrackAudioFeaturesComputed.bpm.isnot(None)
            )
            result = await session.execute(stmt_bpm)
            bpms = [r[0] for r in result.all() if r[0] is not None]

            for bpm in bpms:
                bucket = f"{int(bpm // 10) * 10}-{int(bpm // 10) * 10 + 9}"
                bpm_ranges[bucket] = bpm_ranges.get(bucket, 0) + 1

        # External IDs (YM linked tracks)
        from app.models.track import TrackExternalId

        stmt_ym = select(func.count(TrackExternalId.id)).where(
            TrackExternalId.platform == "yandex_music"
        )
        result = await session.execute(stmt_ym)
        ym_linked = result.scalar() or 0

        return {
            "tracks": {
                "total": total_tracks,
                "active": active_tracks,
                "archived": archived_tracks,
                "with_features": tracks_with_features,
                "without_features": active_tracks - tracks_with_features,
                "feature_coverage": round(tracks_with_features / active_tracks * 100, 1)
                if active_tracks > 0
                else 0.0,
            },
            "playlists": playlist_count,
            "sets": set_count,
            "ym_linked_tracks": ym_linked,
            "bpm_distribution": dict(sorted(bpm_ranges.items())),
        }
