"""Base stem transition policies."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from app.domain.render.stem_policy.models import (
    AvailableData,
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class CompositeStemTransitionPolicy:
    """Applies multiple policies in sequence.

    Each policy receives the output of the previous one.
    Order matters: policies can override fields set by earlier policies.
    """

    def __init__(self, policies: Sequence[StemTransitionPolicy]) -> None:
        self._policies = list(policies)

    def compute(self, ctx: StemTransitionContext) -> FadePlan:
        """Apply all policies to context, returning final fade plan."""
        plan = FadePlan.identity()
        for policy in self._policies:
            try:
                plan = policy.merge(plan, ctx)
            except Exception:
                plan = plan.update(notes=(*plan.notes, f"policy_{policy.name}_failed"))
        return plan

    def __iter__(self) -> Iterator[StemTransitionPolicy]:
        return iter(self._policies)


def default_policy(available: AvailableData) -> CompositeStemTransitionPolicy:
    """Factory for the default policy set — order from design §3.6.

    Each policy mutates only its own fields; order matters.
    Policies that need absent data degrade gracefully (no-op).
    """
    from app.domain.render.stem_policy.policies.base_timbre import BaseTimbrePolicy
    from app.domain.render.stem_policy.policies.beat_strength import BeatStrengthPolicy
    from app.domain.render.stem_policy.policies.beatgrid import BeatgridPolicy
    from app.domain.render.stem_policy.policies.bpm_discrepancy import BpmDiscrepancyPolicy
    from app.domain.render.stem_policy.policies.camelot import CamelotPolicy
    from app.domain.render.stem_policy.policies.cross_similarity import CrossSimilarityPolicy
    from app.domain.render.stem_policy.policies.cue_point import CuePointPolicy
    from app.domain.render.stem_policy.policies.embedding import EmbeddingPolicy
    from app.domain.render.stem_policy.policies.energy_follow import EnergyFollowPolicy
    from app.domain.render.stem_policy.policies.feedback import FeedbackPolicy
    from app.domain.render.stem_policy.policies.phrase_align import PhraseAlignPolicy
    from app.domain.render.stem_policy.policies.scoring_profile import ScoringProfilePolicy
    from app.domain.render.stem_policy.policies.section_pair import SectionPairPolicy
    from app.domain.render.stem_policy.policies.spectral_clash import SpectralClashPolicy
    from app.domain.render.stem_policy.policies.stem_role import StemRolePolicy
    from app.domain.render.stem_policy.policies.subgenre_timing import SubgenreTimingPolicy
    from app.domain.render.stem_policy.policies.transition_recipe import TransitionRecipePolicy
    from app.domain.render.stem_policy.policies.user_history import UserHistoryPolicy
    from app.domain.render.stem_policy.policies.user_override import UserOverridePolicy
    from app.domain.render.stem_policy.policies.vocal_clash import VocalClashPolicy
    from app.domain.render.stem_policy.policies.vocals_cover import VocalsCoverPolicy

    policies: list[StemTransitionPolicy] = [
        BaseTimbrePolicy(),  # 1
        EnergyFollowPolicy(),  # 2 — graceful if no L6
        StemRolePolicy(),  # 6 — always
        SubgenreTimingPolicy(),  # 5
        SpectralClashPolicy(),  # 7
        VocalClashPolicy(),  # 8
        BeatStrengthPolicy(),  # 9
        BpmDiscrepancyPolicy(),  # 10
        # 11 + 12 + 3/4 are data-gated but still instantiated (they no-op if absent)
        BeatgridPolicy(),
        CuePointPolicy(),
        PhraseAlignPolicy(),
        SectionPairPolicy(),
        TransitionRecipePolicy(),  # 13
        UserHistoryPolicy(),  # 14
        FeedbackPolicy(),  # 15
        ScoringProfilePolicy(),  # 16
        EmbeddingPolicy(),  # 17
        CrossSimilarityPolicy(),  # 18
        CamelotPolicy(),  # 19
        VocalsCoverPolicy(),  # 20
        UserOverridePolicy(),  # 21 — always last
    ]
    # Prune policies whose hard data gate is false — keep always-on ones.
    # The graceful policies above already no-op, but pruning keeps compute minimal
    # when the builder knows data is absent (mirrors design §3.7 Min data column).
    if not available.has_beatgrid:
        policies = [p for p in policies if p.name != "beatgrid"]
    if not available.has_cue_points:
        policies = [p for p in policies if p.name != "cue_point"]
    if not available.has_sections:
        policies = [p for p in policies if p.name not in ("phrase_align", "section_pair")]
    if not available.has_transition_recipe:
        policies = [p for p in policies if p.name != "transition_recipe"]
    if not available.has_affinity:
        policies = [p for p in policies if p.name != "user_history"]
    if not available.has_user_feedback:
        policies = [p for p in policies if p.name != "feedback"]
    if not available.has_embedding:
        policies = [p for p in policies if p.name != "embedding"]
    if not available.has_cross_similarity:
        policies = [p for p in policies if p.name != "cross_similarity"]

    return CompositeStemTransitionPolicy(policies)
