"""Curation service — mood classification, playlist audit, distribution, stats.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from typing import Any

from app.audio.mood import MoodClassifier
from app.config import settings
from app.core.constants import TechnoSubgenre
from app.core.errors import NotFoundError, ValidationError
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository


class CurationService:
    """Mood classification, playlist audit, subgenre distribution, library stats."""

    def __init__(
        self,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        set_repo: SetRepository,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
    ) -> None:
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._sets = set_repo
        self._features = feature_repo
        self._transitions = transition_repo

    # ── classify_mood ────────────────────────────────

    async def classify_mood(
        self,
        track_ids: list[int] | None = None,
        playlist_id: int | None = None,
        reclassify: bool = False,
    ) -> dict[str, Any]:
        """Classify tracks by 15 techno subgenres."""
        ids_to_classify: list[int] = list(track_ids or [])
        if playlist_id is not None:
            playlist_track_ids = await self._playlists.get_track_ids(playlist_id)
            ids_to_classify.extend(playlist_track_ids)

        if not ids_to_classify:
            raise ValidationError("No tracks to classify")

        classifier = MoodClassifier()
        classifications: list[dict[str, Any]] = []
        skipped = 0

        for tid in ids_to_classify:
            features = await self._features.get_features(tid)
            if features is None:
                skipped += 1
                continue

            if not reclassify and features.mood is not None:
                skipped += 1
                continue

            feat_dict = features.to_classifier_dict()
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

    # ── audit_playlist ───────────────────────────────

    async def audit_playlist(
        self,
        playlist_id: int | None = None,
        playlist_query: str | None = None,
    ) -> dict[str, Any]:
        """Audit playlist for techno quality criteria and gaps."""
        if playlist_id is None and playlist_query is None:
            raise ValidationError("Provide playlist_id or playlist_query")

        playlist = None
        if playlist_id is not None:
            playlist = await self._playlists.get_with_items(playlist_id)
        elif playlist_query:
            playlist = await self._playlists.search_with_items(playlist_query)

        if playlist is None:
            raise NotFoundError("Playlist", playlist_id or playlist_query)

        track_ids = [item.track_id for item in sorted(playlist.items, key=lambda i: i.sort_index)]
        if not track_ids:
            raise ValidationError("Playlist is empty")

        issues: list[dict[str, Any]] = []
        stats: dict[str, Any] = {
            "total_tracks": len(track_ids),
            "with_features": 0,
            "without_features": 0,
        }
        bpm_values: list[float] = []
        energy_values: list[float] = []

        for tid in track_ids:
            track = await self._tracks.get_by_id(tid)
            if track is None:
                issues.append({"track_id": tid, "issue": "track_missing", "severity": "error"})
                continue

            features = await self._features.get_features(tid)
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

    # ── review_set_quality ───────────────────────────

    async def review_set_quality(
        self,
        set_id: int,
        version_label: str | None = None,
    ) -> dict[str, Any]:
        """Review set quality: transitions, BPM flow, energy arc."""
        dj_set = await self._sets.get_by_id(set_id)
        if dj_set is None:
            raise NotFoundError("Set", set_id)

        target_version = None
        if version_label:
            target_version = await self._sets.get_version_by_label(set_id, version_label)
        else:
            target_version = await self._sets.get_latest_version(set_id)

        if target_version is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")

        items = await self._sets.get_version_items(target_version.id)
        if not items:
            raise ValidationError("Set is empty")

        bpm_flow: list[float | None] = []
        energy_flow: list[float | None] = []
        for item in items:
            features = await self._features.get_features(item.track_id)
            if features:
                bpm_flow.append(features.bpm)
                energy_flow.append(features.energy_mean)
            else:
                bpm_flow.append(None)
                energy_flow.append(None)

        transition_scores: list[float | None] = []
        hard_conflicts = 0
        weak_transitions = 0

        for i in range(len(items) - 1):
            score = await self._transitions.get_score(items[i].track_id, items[i + 1].track_id)
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

        valid_bpms = [b for b in bpm_flow if b is not None]
        bpm_jumps = 0
        if len(valid_bpms) > 1:
            for i in range(len(valid_bpms) - 1):
                if (
                    abs(valid_bpms[i] - valid_bpms[i + 1])
                    > settings.transition_hard_reject_bpm_diff
                ):
                    bpm_jumps += 1

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

    # ── distribute_to_subgenres ──────────────────────

    async def distribute_to_subgenres(
        self,
        source_playlist_id: int | None = None,
        mode: str = "append",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Distribute tracks to 15 subgenre playlists based on mood."""
        if source_playlist_id is not None:
            track_ids = await self._playlists.get_track_ids(source_playlist_id)
        else:
            track_ids = await self._tracks.get_active_track_ids()

        if not track_ids:
            raise ValidationError("No tracks to distribute")

        classifier = MoodClassifier()
        distribution: dict[str, list[int]] = {sg.value: [] for sg in TechnoSubgenre}
        skipped = 0

        for tid in track_ids:
            features = await self._features.get_features(tid)
            if features is None:
                skipped += 1
                continue
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

        created_playlists = 0
        total_assigned = 0

        for subgenre in TechnoSubgenre:
            sg_track_ids = distribution[subgenre.value]
            if not sg_track_ids:
                continue

            playlist_name = f"Subgenre: {subgenre.value}"
            playlist, is_new = await self._playlists.get_or_create_by_name(playlist_name)
            if is_new:
                created_playlists += 1

            if mode == "clean_rebuild":
                await self._playlists.clear_items(playlist.id)
                start_idx = 0
            else:
                start_idx = await self._playlists.get_max_sort_index(playlist.id) + 1

            for i, tid in enumerate(sg_track_ids):
                await self._playlists.add_track(playlist.id, tid, start_idx + i)
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

    # ── get_library_stats ────────────────────────────

    async def get_library_stats(self) -> dict[str, Any]:
        """Library dashboard: counts, coverage, distributions."""
        return await self._tracks.get_library_stats()
