"""Stem transition policies."""

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

__all__ = [
    "BaseTimbrePolicy",
    "BeatStrengthPolicy",
    "BeatgridPolicy",
    "BpmDiscrepancyPolicy",
    "CamelotPolicy",
    "CrossSimilarityPolicy",
    "CuePointPolicy",
    "EmbeddingPolicy",
    "EnergyFollowPolicy",
    "FeedbackPolicy",
    "PhraseAlignPolicy",
    "ScoringProfilePolicy",
    "SectionPairPolicy",
    "SpectralClashPolicy",
    "StemRolePolicy",
    "SubgenreTimingPolicy",
    "TransitionRecipePolicy",
    "UserHistoryPolicy",
    "UserOverridePolicy",
    "VocalClashPolicy",
    "VocalsCoverPolicy",
]
