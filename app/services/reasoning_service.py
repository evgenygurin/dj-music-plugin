"""Reasoning service — suggest, explain, replace, compare, quick review.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from typing import Any

from app.camelot.wheel import camelot_distance, key_code_to_camelot
from app.core.errors import NotFoundError, ValidationError
from app.db.models.set import SetVersion
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.db.repositories.transition import TransitionRepository
from app.transition import TransitionScorer

_ENERGY_DIRECTIONS: frozenset[str] = frozenset({"any", "up", "down"})

#: Multiplicative bonus/penalty applied per LUFS delta when the caller
#: requests a specific energy direction. Tuned so that a +3 LUFS lift
#: is ~9% boost — enough to re-order otherwise-tied candidates without
#: dominating the underlying transition score.
_ENERGY_PREFERENCE_WEIGHT: float = 0.03


def _apply_energy_preference(
    overall: float,
    *,
    current_lufs: float | None,
    candidate_lufs: float | None,
    direction: str,
) -> float:
    """Nudge an overall transition score toward the preferred energy direction."""
    if direction == "any" or current_lufs is None or candidate_lufs is None:
        return overall
    delta = candidate_lufs - current_lufs
    bonus = delta * _ENERGY_PREFERENCE_WEIGHT
    if direction == "down":
        bonus = -bonus
    return max(0.0, min(1.0, overall + bonus))


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
        prefer_mood: str | None = None,
        energy_direction: str = "any",
    ) -> dict[str, Any]:
        """Suggest best tracks for a set position, scored against both neighbours.

        Parameters
        ----------
        prefer_mood:
            Optional subgenre filter — only candidates whose classified
            mood matches are considered.
        energy_direction:
            ``"up"`` boosts candidates with higher integrated LUFS than
            the current track, ``"down"`` boosts lower-LUFS ones,
            ``"any"`` leaves the transition score untouched.
        """
        if energy_direction not in _ENERGY_DIRECTIONS:
            raise ValidationError(
                f"Invalid energy_direction: {energy_direction!r}. "
                f"Expected one of {sorted(_ENERGY_DIRECTIONS)}",
                field="energy_direction",
                value=energy_direction,
            )

        result = await self._sets.load_version_with_items(set_id)
        if result is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        _, items = result

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
            pool_ids_raw = await self._features.get_all_track_ids_with_features()
            pool_ids = [tid for tid in pool_ids_raw if tid not in set_track_ids]

        # Exclude banned tracks (Phase 3 AI intelligence)
        try:
            from app.db.repositories.track_feedback import TrackFeedbackRepository

            feedback_repo = TrackFeedbackRepository(self._tracks.session)
            banned_ids = set(await feedback_repo.get_banned_ids())
            if banned_ids:
                pool_ids = [tid for tid in pool_ids if tid not in banned_ids]
        except Exception:
            pass  # Feedback is non-critical

        features_map = await self._features.get_scoring_features_batch(pool_ids[:100])

        scorer = TransitionScorer()
        current_lufs = current_feat.integrated_lufs
        candidates: list[dict[str, Any]] = []
        mood_filter = prefer_mood.lower() if prefer_mood else None

        for tid, cand_feat in features_map.items():
            if cand_feat.bpm is None:
                continue
            if mood_filter is not None:
                cand_mood = (cand_feat.mood or "").lower()
                if cand_mood != mood_filter:
                    continue

            score = scorer.score(current_feat, cand_feat)
            if score.hard_reject:
                continue

            adjusted = _apply_energy_preference(
                score.overall,
                current_lufs=current_lufs,
                candidate_lufs=cand_feat.integrated_lufs,
                direction=energy_direction,
            )

            track = await self._tracks.get_by_id(tid)
            candidates.append(
                {
                    "track_id": tid,
                    "title": track.title if track else f"#{tid}",
                    "score": round(adjusted, 4),
                    "base_score": round(score.overall, 4),
                    "bpm": cand_feat.bpm,
                    "key_code": cand_feat.key_code,
                    "mood": cand_feat.mood,
                    "lufs": cand_feat.integrated_lufs,
                }
            )

        candidates.sort(key=lambda c: float(str(c["score"])), reverse=True)

        return {
            "set_id": set_id,
            "after_position": after_position,
            "current_track": current_track.title if current_track else None,
            "prefer_mood": prefer_mood,
            "energy_direction": energy_direction,
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
                "timbral": score.timbral_score,
                "hard_reject": bool(score.hard_reject) if score.hard_reject is not None else False,
                "reject_reason": score.reject_reason,
            }

        return explanation

    async def compare_set_versions(
        self,
        set_id: int,
        version_a: int | None = None,
        version_b: int | None = None,
    ) -> dict[str, Any]:
        """Compare two versions of a set: tracks added/removed, score changes."""
        ver_a: SetVersion | None
        ver_b: SetVersion | None
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

    async def find_replacement(
        self,
        set_id: int,
        position: int,
        count: int = 5,
    ) -> dict[str, Any]:
        """Find replacement tracks for a position, scored against both neighbours.

        For an interior position the candidate must transition cleanly
        from ``items[position-1]`` *and* into ``items[position+1]``; the
        score is the average of both. Edge positions use only the one
        existing neighbour.
        """
        result = await self._sets.load_version_with_items(set_id)
        if result is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        _, items = result

        if not items:
            raise ValidationError("Set is empty")
        if position < 0 or position >= len(items):
            raise ValidationError(f"Position {position} out of range (0-{len(items) - 1})")

        prev_item = items[position - 1] if position > 0 else None
        next_item = items[position + 1] if position + 1 < len(items) else None
        current_item = items[position]

        prev_feat = (
            await self._features.get_scoring_features(prev_item.track_id) if prev_item else None
        )
        next_feat = (
            await self._features.get_scoring_features(next_item.track_id) if next_item else None
        )

        dj_set = await self._sets.get_by_id(set_id)
        if not dj_set:
            raise NotFoundError("Set", set_id)

        set_track_ids = {item.track_id for item in items}
        if dj_set.source_playlist_id:
            pool_ids = await self._playlists.get_track_ids(dj_set.source_playlist_id)
        else:
            pool_ids = await self._features.get_all_track_ids_with_features()
        pool_ids = [tid for tid in pool_ids if tid not in set_track_ids]

        features_map = await self._features.get_scoring_features_batch(pool_ids[:200])

        scorer = TransitionScorer()
        candidates: list[dict[str, Any]] = []
        for tid, cand_feat in features_map.items():
            if cand_feat.bpm is None:
                continue

            scores: list[float] = []
            hard_reject = False

            if prev_feat is not None:
                s_in = scorer.score(prev_feat, cand_feat)
                if s_in.hard_reject:
                    hard_reject = True
                else:
                    scores.append(s_in.overall)

            if next_feat is not None:
                s_out = scorer.score(cand_feat, next_feat)
                if s_out.hard_reject:
                    hard_reject = True
                else:
                    scores.append(s_out.overall)

            if hard_reject or not scores:
                continue

            avg = sum(scores) / len(scores)
            track = await self._tracks.get_by_id(tid)
            candidates.append(
                {
                    "track_id": tid,
                    "title": track.title if track else f"#{tid}",
                    "score": round(avg, 4),
                    "bpm": cand_feat.bpm,
                    "key_code": cand_feat.key_code,
                    "mood": cand_feat.mood,
                    "lufs": cand_feat.integrated_lufs,
                }
            )

        candidates.sort(key=lambda c: float(str(c["score"])), reverse=True)

        return {
            "set_id": set_id,
            "position": position,
            "current_track_id": current_item.track_id,
            "pool_size": len(pool_ids),
            "scored": len(candidates),
            "candidates": candidates[:count],
        }

    async def quick_set_review(self, set_id: int) -> dict[str, Any]:
        """Quick set review: tracks and basic quality info."""
        dj_set = await self._sets.get_by_id(set_id)
        if not dj_set:
            raise NotFoundError("Set", set_id)

        result = await self._sets.load_version_with_items(set_id)
        if result is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        latest, items = result

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
