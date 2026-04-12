"""CurationService facade — backward-compatible API over sub-services."""

from __future__ import annotations

from typing import Any

from dj_music.repositories.feature import FeatureRepository
from dj_music.repositories.playlist import PlaylistRepository
from dj_music.repositories.set import SetRepository
from dj_music.repositories.track import TrackRepository
from dj_music.repositories.transition import TransitionRepository
from dj_music.services.curation.audit import PlaylistAuditService
from dj_music.services.curation.distribution import DistributionService
from dj_music.services.curation.mood import MoodClassificationService


class CurationService:
    """Facade: mood classification, playlist audit, subgenre distribution, library stats."""

    def __init__(
        self,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        set_repo: SetRepository,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
    ) -> None:
        self._tracks = track_repo
        self._sets = set_repo
        self._features = feature_repo
        self._transitions = transition_repo
        self._mood = MoodClassificationService(feature_repo, playlist_repo)
        self._audit = PlaylistAuditService(track_repo, playlist_repo, feature_repo)
        self._distribution = DistributionService(track_repo, playlist_repo, feature_repo)

    async def classify_mood(
        self,
        track_ids: list[int] | None = None,
        playlist_id: int | None = None,
        reclassify: bool = False,
    ) -> dict[str, Any]:
        return await self._mood.classify_mood(track_ids, playlist_id, reclassify)

    async def audit_playlist(
        self,
        playlist_id: int | None = None,
        playlist_query: str | None = None,
    ) -> dict[str, Any]:
        return await self._audit.audit_playlist(playlist_id, playlist_query)

    async def review_set_quality(
        self,
        set_id: int,
        version_label: str | None = None,
    ) -> dict[str, Any]:
        """Review set quality: transitions, BPM flow, energy arc."""
        from dj_music.core.config import settings
        from dj_music.core.errors import NotFoundError, ValidationError

        dj_set = await self._sets.get_by_id(set_id)
        if dj_set is None:
            raise NotFoundError("Set", set_id)

        result = await self._sets.load_version_with_items(set_id, version_label)
        if result is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        target_version, items = result

        if not items:
            raise ValidationError("Set is empty")

        # Batch-load features for all set tracks (N queries → 1)
        item_track_ids = [item.track_id for item in items]
        features_map = await self._features.get_features_batch(item_track_ids)

        bpm_flow: list[float | None] = []
        energy_flow: list[float | None] = []
        for item in items:
            features = features_map.get(item.track_id)
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

        # Rating heuristic — hard conflicts are non-negotiable: any
        # ``hard_reject`` transition means we cannot mix the set as
        # planned without violating BPM/key/energy constraints. We
        # also penalise sets where hard conflicts dominate the few
        # transitions we do have (e.g. 1/1 = 100% broken).
        total_transitions = max(len(items) - 1, 0)
        hard_conflict_ratio = hard_conflicts / total_transitions if total_transitions > 0 else 0.0

        if hard_conflict_ratio >= 0.5 or (hard_conflicts >= 1 and total_transitions <= 2):
            rating = "poor"
        elif hard_conflicts >= 1:
            rating = "fair"
        elif not quality_issues:
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

    async def distribute_to_subgenres(
        self,
        source_playlist_id: int | None = None,
        mode: str = "append",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return await self._distribution.distribute_to_subgenres(source_playlist_id, mode, dry_run)

    async def get_library_stats(self) -> dict[str, Any]:
        return await self._tracks.get_library_stats()
