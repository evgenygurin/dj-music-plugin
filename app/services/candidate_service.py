"""Transition candidate service — pre-filter track pairs for scoring.

Reduces O(n^2) pair space by applying BPM, key, and energy filters.
See docs/transition-scoring.md § Optimization: Pruning Candidate Pairs.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.config import settings
from app.core.camelot import camelot_distance
from app.db.models.transition import TransitionCandidate
from app.transition import TransitionScorer

if TYPE_CHECKING:
    from app.db.repositories.candidate import CandidateRepository


@dataclass
class CandidateStats:
    """Statistics from a candidate generation run."""

    total_tracks: int
    total_pairs_checked: int
    candidates_created: int
    skipped_missing_features: int


# Maximum Camelot distance for candidate inclusion (tighter than hard reject of 5).
_CANDIDATE_KEY_DISTANCE_MAX = 2


class CandidateService:
    """Pre-filter track pairs for transition scoring.

    For each pair of tracks, checks:
    - BPM within ±settings.transition_hard_reject_bpm_diff
    - Camelot distance ≤ 2 (stricter than hard reject of 5)
    - Energy gap within ±settings.transition_hard_reject_energy_gap LUFS
    """

    def __init__(self, repo: CandidateRepository) -> None:
        self._repo = repo
        self._scorer = TransitionScorer()

    async def generate_candidates(
        self,
        track_ids: list[int] | None = None,
    ) -> CandidateStats:
        """Generate transition candidates for given tracks (or all tracks).

        Loads all TrackAudioFeaturesComputed in one batch query,
        then checks each pair against BPM/key/energy filters.
        Saves matching pairs as TransitionCandidate records.

        Args:
            track_ids: Specific tracks to generate candidates for.
                       If None, uses all tracks with features.

        Returns:
            Statistics about the generation run.
        """
        # 1. Load features in one batch query
        features_map = await self._repo.load_features(track_ids)

        valid_ids = sorted(features_map.keys())
        skipped = (len(track_ids) - len(valid_ids)) if track_ids else 0

        if len(valid_ids) < 2:
            return CandidateStats(
                total_tracks=len(valid_ids),
                total_pairs_checked=0,
                candidates_created=0,
                skipped_missing_features=skipped,
            )

        # 2. Delete existing candidates for these tracks to regenerate
        await self._repo.delete_candidates_for_tracks(valid_ids)

        # 3. Check all pairs and collect candidates
        bpm_threshold = settings.transition_hard_reject_bpm_diff
        energy_threshold = settings.transition_hard_reject_energy_gap

        candidates: list[TransitionCandidate] = []
        pairs_checked = 0

        for id_a, id_b in itertools.combinations(valid_ids, 2):
            pairs_checked += 1
            feat_a = features_map[id_a]
            feat_b = features_map[id_b]

            # BPM filter
            bpm_dist = self._bpm_distance(feat_a.bpm, feat_b.bpm)
            if bpm_dist is None or bpm_dist > bpm_threshold:
                continue

            # Key filter
            key_dist = self._key_distance(feat_a.key_code, feat_b.key_code)
            if key_dist is None or key_dist > _CANDIDATE_KEY_DISTANCE_MAX:
                continue

            # Energy filter
            energy_delta = self._energy_delta(feat_a.integrated_lufs, feat_b.integrated_lufs)
            if energy_delta is None or energy_delta > energy_threshold:
                continue

            # Both directions (A→B and B→A) are valid transitions
            candidates.append(
                TransitionCandidate(
                    from_track_id=id_a,
                    to_track_id=id_b,
                    bpm_distance=bpm_dist,
                    key_distance=key_dist,
                    energy_delta=energy_delta,
                    fully_scored=False,
                )
            )
            candidates.append(
                TransitionCandidate(
                    from_track_id=id_b,
                    to_track_id=id_a,
                    bpm_distance=bpm_dist,
                    key_distance=key_dist,
                    energy_delta=energy_delta,
                    fully_scored=False,
                )
            )

        # 4. Bulk insert candidates
        await self._repo.bulk_insert(candidates)

        return CandidateStats(
            total_tracks=len(valid_ids),
            total_pairs_checked=pairs_checked,
            candidates_created=len(candidates),
            skipped_missing_features=skipped,
        )

    async def get_candidates_for_track(
        self,
        track_id: int,
        limit: int = 20,
    ) -> list[TransitionCandidate]:
        """Get pre-filtered candidates for a specific track, ordered by BPM distance."""
        return await self._repo.get_candidates_for_track(track_id, limit)

    async def get_candidate_pair(
        self,
        from_track_id: int,
        to_track_id: int,
    ) -> TransitionCandidate | None:
        """Get a specific candidate pair, or None if it doesn't exist."""
        return await self._repo.get_candidate_pair(from_track_id, to_track_id)

    async def count_candidates(self, track_id: int | None = None) -> int:
        """Count total candidates, optionally for a specific track."""
        return await self._repo.count_candidates(track_id)

    # ── Internal helpers ─────────────────────────────────

    @staticmethod
    def _bpm_distance(bpm_a: float | None, bpm_b: float | None) -> float | None:
        """BPM distance with double/half-time awareness, or None if data missing."""
        from app.transition.math_helpers import bpm_distance

        if bpm_a is None or bpm_b is None:
            return None
        return bpm_distance(bpm_a, bpm_b)

    @staticmethod
    def _key_distance(key_a: int | None, key_b: int | None) -> int | None:
        """Camelot distance, or None if data missing."""
        if key_a is None or key_b is None:
            return None
        return camelot_distance(key_a, key_b)

    @staticmethod
    def _energy_delta(lufs_a: float | None, lufs_b: float | None) -> float | None:
        """Absolute LUFS difference, or None if data missing."""
        if lufs_a is None or lufs_b is None:
            return None
        return abs(lufs_a - lufs_b)
