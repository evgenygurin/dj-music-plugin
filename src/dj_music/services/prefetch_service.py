"""Speculative prefetch service — proactively prepare the *next* track.

Rationale: as soon as a track transition is locked in (user just picked track A
to be the next cue), the DJ workflow already knows *roughly* which tracks will
be considered next. Instead of waiting until the next ``suggest_next_track``
call to do the work sequentially, we can overlap it with "thinking time":

1. Pre-score seed → top-K candidates via :class:`TransitionScorer` and persist
   the full 6-component breakdown so the next scoring loop hits cached rows
   (O(1) DB lookup instead of full component recomputation).
2. Ensure L3 (SCORING) audio features exist for the top-K pool so the next
   call to ``suggest_next_track`` / ``build_set`` / ``score_transitions`` does
   not block on a 7-second-per-track analyzer run.

The service is framework-agnostic: no MCP imports, no access to FastMCP
``Context``. Tools wire it up via ``Depends(get_prefetch_service)`` and call
``prefetch_after(...)`` directly — the work runs inline (not fire-and-forget)
because the per-request DB session closes when the tool returns. Spawning an
``asyncio.create_task`` that uses the same session would race the commit.

Performance: prefetch is cheap because everything stays in the hot path of an
already-open request. A single batch query loads all features; scoring is pure
math (~0.1ms/pair); the only heavy optional step is ``ensure_level`` for L3,
which is gated by ``settings.prefetch_analysis_budget`` so it never blocks the
return value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dj_music.audio.level_config import AnalysisLevel
from dj_music.core.config import settings
from app.db.models.transition import Transition
from app.entities.audio.features import TrackFeatures
from dj_music.transition import TransitionScorer

if TYPE_CHECKING:
    from app.db.repositories.feature import FeatureRepository
    from app.db.repositories.transition import TransitionRepository
    from dj_music.services.tiered_pipeline import TieredPipeline


@dataclass
class PrefetchResult:
    """Summary of work performed during a speculative prefetch call."""

    seed_track_id: int
    candidates_considered: int
    pairs_scored: int
    pairs_cached_hit: int
    analysis_scheduled: int
    analysis_skipped: int
    hard_rejects: int
    top_candidate_ids: list[int]


class PrefetchService:
    """Proactively prepare candidates after a track transition.

    All methods are framework-agnostic and safe to call from any tool running
    within a normal request scope. The service never spawns background tasks
    that outlive the caller's DB session — every awaited call completes before
    returning, so the transaction boundary stays aligned with the tool call.
    """

    def __init__(
        self,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
        tiered_pipeline: TieredPipeline | None = None,
    ) -> None:
        self._features = feature_repo
        self._transitions = transition_repo
        self._tiered = tiered_pipeline
        self._scorer = TransitionScorer()

    async def prefetch_after(
        self,
        seed_track_id: int,
        pool_ids: list[int],
        *,
        top_k: int = 10,
        ensure_analysis_level: AnalysisLevel | None = None,
        persist_scores: bool = True,
    ) -> PrefetchResult:
        """Prepare candidates for the transition *after* ``seed_track_id``.

        Pipeline:

        1. **Feature batch-load** — one SQL round-trip pulls scoring features
           for the seed plus the full pool.
        2. **Fast filter** — candidates without a BPM are dropped; the rest are
           scored against the seed with :class:`TransitionScorer`. Hard rejects
           (BPM/key/energy) are counted and excluded.
        3. **Warm transition cache** — top-K pairs are checked for existing
           rows in ``transitions`` (single batch query), and missing pairs are
           inserted via ``save_scores_bulk`` so the *next* ``score_pair`` call
           hits the cache.
        4. **Schedule L3 analysis** — if a :class:`TieredPipeline` is wired,
           the top-K candidate IDs missing SCORING-level features are handed
           off via ``ensure_level``. Bounded by ``prefetch_analysis_budget``.

        Args:
            seed_track_id: The freshly-locked-in track. Candidates are scored
                against this track's features.
            pool_ids: Track IDs to consider as next candidates. Typically the
                source playlist minus tracks already in the set.
            top_k: How many top-scored candidates to warm and (optionally)
                schedule for analysis.
            ensure_analysis_level: If set, triggers tiered analysis so the
                next scoring call doesn't stall.
            persist_scores: If ``False``, compute in-memory only. Useful for
                tests or when you only want the top-K list without DB writes.
        """
        if not pool_ids:
            return _empty_result(seed_track_id)

        seed_feat = await self._features.get_scoring_features(seed_track_id)
        if seed_feat is None or seed_feat.bpm is None:
            return _empty_result(seed_track_id)

        unique_pool = [tid for tid in dict.fromkeys(pool_ids) if tid != seed_track_id]
        features_map = await self._features.get_scoring_features_batch(unique_pool)

        scored_pairs: list[tuple[int, float, TrackFeatures]] = []
        hard_rejects = 0
        for tid, feat in features_map.items():
            if feat.bpm is None:
                continue
            score = self._scorer.score(seed_feat, feat)
            if score.hard_reject:
                hard_rejects += 1
                continue
            scored_pairs.append((tid, score.overall, feat))

        scored_pairs.sort(key=lambda item: item[1], reverse=True)
        top_ids = [tid for tid, _score, _feat in scored_pairs[:top_k]]

        cached_hits = 0
        if persist_scores and top_ids:
            cached_hits = await self._warm_transition_cache(seed_track_id, seed_feat, top_ids)

        analysis_scheduled = 0
        analysis_skipped = 0
        if ensure_analysis_level is not None and self._tiered is not None and top_ids:
            stats = await self._ensure_level_bounded(top_ids, ensure_analysis_level)
            analysis_scheduled = stats["analyzed"]
            analysis_skipped = stats["skipped"]

        return PrefetchResult(
            seed_track_id=seed_track_id,
            candidates_considered=len(features_map),
            pairs_scored=len(scored_pairs),
            pairs_cached_hit=cached_hits,
            analysis_scheduled=analysis_scheduled,
            analysis_skipped=analysis_skipped,
            hard_rejects=hard_rejects,
            top_candidate_ids=top_ids,
        )

    async def _warm_transition_cache(
        self,
        seed_track_id: int,
        seed_feat: TrackFeatures,
        candidate_ids: list[int],
    ) -> int:
        """Persist any missing ``seed → candidate`` scores in one flush.

        Returns the number of pairs that already had a cached row (skipped).
        Missing pairs are recomputed once and saved via ``save_scores_bulk``.
        """
        cached = await self._transitions.get_scores_for_seed(seed_track_id, candidate_ids)
        missing_ids = [tid for tid in candidate_ids if tid not in cached]
        if not missing_ids:
            return len(cached)

        features_map = await self._features.get_scoring_features_batch(missing_ids)
        new_rows: list[Transition] = []
        for tid in missing_ids:
            feat = features_map.get(tid)
            if feat is None or feat.bpm is None:
                continue
            score = self._scorer.score(seed_feat, feat)
            hard = score.hard_reject
            new_rows.append(
                Transition(
                    from_track_id=seed_track_id,
                    to_track_id=tid,
                    overall_quality=0.0 if hard else score.overall,
                    bpm_score=score.bpm,
                    harmonic_score=score.harmonic,
                    energy_score=score.energy,
                    spectral_score=score.spectral,
                    groove_score=score.groove,
                    timbral_score=score.timbral,
                    hard_reject=hard,
                    reject_reason=score.reject_reason,
                )
            )

        await self._transitions.save_scores_bulk(new_rows)
        return len(cached)

    async def _ensure_level_bounded(
        self,
        track_ids: list[int],
        level: AnalysisLevel,
    ) -> dict[str, int]:
        """Delegate to ``TieredPipeline.ensure_level`` with a budget.

        The budget is ``settings.prefetch_analysis_budget``: high enough to
        cover the top-K warm list but low enough that a speculative call never
        monopolises the download workers. Falls back to the raw top-K list
        when the setting is unset.
        """
        budget = getattr(settings, "prefetch_analysis_budget", len(track_ids))
        bounded = track_ids[: max(1, budget)]
        assert self._tiered is not None  # type narrowing
        try:
            return await self._tiered.ensure_level(bounded, level)
        except Exception:
            # Prefetch is best-effort: never propagate analysis failures to
            # the caller. The next scoring call falls back to live analysis.
            return {"analyzed": 0, "skipped": len(bounded), "failed": len(bounded)}


def _empty_result(seed_track_id: int) -> PrefetchResult:
    """Zeroed result used when the prefetch is a no-op (empty pool or no features)."""
    return PrefetchResult(
        seed_track_id=seed_track_id,
        candidates_considered=0,
        pairs_scored=0,
        pairs_cached_hit=0,
        analysis_scheduled=0,
        analysis_skipped=0,
        hard_rejects=0,
        top_candidate_ids=[],
    )
