"""Reasoning service — suggest, explain, replace, compare, quick review.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from typing import Any

from app.core.camelot import camelot_distance, key_code_to_camelot
from app.core.errors import NotFoundError, ValidationError
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.transition import TransitionScorer


class ReasoningService:
    """DJ-specific reasoning: suggestions, explanations, comparisons."""

    def __init__(
        self,
        set_repo: SetRepository,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
    ) -> None:
        self._sets = set_repo
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._features = feature_repo
        self._transitions = transition_repo

    async def suggest_next_track(
        self,
        set_id: int,
        after_position: int,
        count: int = 5,
    ) -> dict[str, Any]:
        """Suggest best tracks for a set position, scored against both neighbors."""
        latest = await self._sets.get_latest_version(set_id)
        if not latest:
            raise NotFoundError("SetVersion", f"set_id={set_id}")

        items = await self._sets.get_version_items(latest.id)

        if after_position < 0 or after_position >= len(items):
            raise ValidationError(f"Position {after_position} out of range (0-{len(items) - 1})")

        current_item = items[after_position]
        current_track = await self._tracks.get_by_id(current_item.track_id)
        current_feat = await self._features.get_scoring_features(current_item.track_id)

        if not current_feat or current_feat.bpm is None:
            return {
                "set_id": set_id,
                "after_position": after_position,
                "current_track": current_track.title if current_track else None,
                "suggestions": [],
                "note": "Current track has no audio features — analyze first",
            }

        set_track_ids = {item.track_id for item in items}
        dj_set = await self._sets.get_by_id(set_id)
        if not dj_set:
            raise NotFoundError("Set", set_id)

        if dj_set.source_playlist_id:
            pool_ids = await self._playlists.get_track_ids(dj_set.source_playlist_id)
            pool_ids = [tid for tid in pool_ids if tid not in set_track_ids]
        else:
            pool_ids = await self._features.get_all_track_ids_with_features()
            pool_ids = [tid for tid in pool_ids if tid not in set_track_ids]

        features_map = await self._features.get_scoring_features_batch(pool_ids[:100])

        scorer = TransitionScorer()
        candidates = []
        for tid, cand_feat in features_map.items():
            if cand_feat.bpm is None:
                continue
            score = scorer.score(current_feat, cand_feat)
            if not score.hard_reject:
                track = await self._tracks.get_by_id(tid)
                candidates.append(
                    {
                        "track_id": tid,
                        "title": track.title if track else f"#{tid}",
                        "score": round(score.overall, 4),
                        "bpm": cand_feat.bpm,
                        "key_code": cand_feat.key_code,
                    }
                )

        candidates.sort(key=lambda c: c["score"], reverse=True)

        return {
            "set_id": set_id,
            "after_position": after_position,
            "current_track": current_track.title if current_track else None,
            "suggestions": candidates[:count],
            "pool_size": len(pool_ids),
            "scored": len(candidates),
        }

    async def explain_transition(
        self,
        from_track_id: int,
        to_track_id: int,
    ) -> dict[str, Any]:
        """Explain why a transition works or doesn't — 5-component breakdown."""
        from_track = await self._tracks.get_by_id(from_track_id)
        to_track = await self._tracks.get_by_id(to_track_id)

        if not from_track or not to_track:
            raise NotFoundError("Track", f"{from_track_id} or {to_track_id}")

        score = await self._transitions.get_score(from_track_id, to_track_id)

        from_feat = await self._features.get_features(from_track_id)
        to_feat = await self._features.get_features(to_track_id)

        explanation: dict[str, Any] = {
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

    async def compare_set_versions(
        self,
        set_id: int,
        version_a: int | None = None,
        version_b: int | None = None,
    ) -> dict[str, Any]:
        """Compare two versions of a set: tracks added/removed, score changes."""
        if version_a is None or version_b is None:
            versions = await self._sets.get_latest_versions(set_id, count=2)
            if len(versions) < 2:
                raise ValidationError("Need at least 2 versions to compare")
            ver_b, ver_a = versions[0], versions[1]
        else:
            ver_a = await self._sets.get_version_with_items(version_a)
            ver_b = await self._sets.get_version_with_items(version_b)

        if not ver_a or not ver_b:
            raise NotFoundError("SetVersion", f"{version_a} or {version_b}")

        items_a = await self._sets.get_version_items(ver_a.id)
        items_b = await self._sets.get_version_items(ver_b.id)
        tracks_a = {item.track_id for item in items_a}
        tracks_b = {item.track_id for item in items_b}

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

    async def quick_set_review(self, set_id: int) -> dict[str, Any]:
        """Quick set review: tracks and basic quality info."""
        dj_set = await self._sets.get_by_id(set_id)
        if not dj_set:
            raise NotFoundError("Set", set_id)

        latest = await self._sets.get_latest_version(set_id)
        if not latest:
            raise NotFoundError("SetVersion", f"set_id={set_id}")

        items = await self._sets.get_version_items(latest.id)

        tracks_summary = []
        for item in items:
            track = await self._tracks.get_by_id(item.track_id)
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
