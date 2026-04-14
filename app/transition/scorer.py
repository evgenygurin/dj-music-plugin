"""Transition scoring engine — orchestrator for the 6-component formula.

Pure domain logic: no I/O, no DB, no async. The actual scoring lives in
``app/transition/components/`` (one pure function per component);
this file only checks hard constraints, dispatches to the components,
and combines the results with weights.

See docs/transition-scoring.md for the full algorithm description and
docs/superpowers/specs/2026-04-08-transition-system-redesign.md for the
redesign that produced this layout.
"""

from __future__ import annotations

from app.core.constants import DEFAULT_TRANSITION_WEIGHTS, SectionType
from app.entities.audio.features import TrackFeatures
from app.transition.components import (
    score_bpm,
    score_energy,
    score_groove,
    score_harmonic,
    score_spectral,
    score_timbral,
)
from app.camelot.wheel import camelot_distance
from app.config import settings
from app.transition.constants import (
    DRUM_ONLY_WEIGHT_OVERRIDE,
    GROOVE_CONFLICT_THRESHOLD,
    VOCAL_PITCH_SALIENCE_THRESHOLD,
    VOCAL_SPECTRAL_CENTROID_FLOOR_HZ,
)
from app.transition.intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.transition.math_helpers import bpm_distance
from app.transition.models import ConstraintResult, SectionContext, TransitionScore

__all__ = [
    "TransitionScore",
    "TransitionScorer",
]


def check_hard_constraints(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    pre_bpm_dist: float | None = None,
    pre_key_dist: int | None = None,
    pre_energy_delta: float | None = None,
) -> ConstraintResult:
    """Gate: reject pairs that violate hard constraints; detect soft conflicts."""
    bpm_diff: float | None
    if pre_bpm_dist is not None:
        bpm_diff = pre_bpm_dist
    elif from_t.bpm is not None and to_t.bpm is not None:
        bpm_diff = bpm_distance(from_t.bpm, to_t.bpm)
    else:
        bpm_diff = None

    if bpm_diff is not None and bpm_diff > settings.transition_hard_reject_bpm_diff:
        return ConstraintResult(
            rejection=TransitionScore(
                hard_reject=True,
                reject_reason=f"BPM diff {bpm_diff:.1f} > {settings.transition_hard_reject_bpm_diff}",
            )
        )

    key_dist: int | None
    if pre_key_dist is not None:
        key_dist = pre_key_dist
    elif from_t.key_code is not None and to_t.key_code is not None:
        key_dist = camelot_distance(from_t.key_code, to_t.key_code)
    else:
        key_dist = None

    if key_dist is not None and key_dist >= settings.transition_hard_reject_camelot_dist:
        return ConstraintResult(
            rejection=TransitionScore(
                hard_reject=True,
                reject_reason=f"Camelot distance {key_dist} >= {settings.transition_hard_reject_camelot_dist}",
            )
        )

    energy_gap: float | None
    if pre_energy_delta is not None:
        energy_gap = pre_energy_delta
    elif from_t.integrated_lufs is not None and to_t.integrated_lufs is not None:
        energy_gap = abs(from_t.integrated_lufs - to_t.integrated_lufs)
    else:
        energy_gap = None

    if energy_gap is not None and energy_gap > settings.transition_hard_reject_energy_gap:
        return ConstraintResult(
            rejection=TransitionScore(
                hard_reject=True,
                reject_reason=f"Energy gap {energy_gap:.1f} LUFS > {settings.transition_hard_reject_energy_gap}",
            )
        )

    vocal_conflict = (
        from_t.pitch_salience_mean is not None
        and to_t.pitch_salience_mean is not None
        and from_t.pitch_salience_mean > VOCAL_PITCH_SALIENCE_THRESHOLD
        and to_t.pitch_salience_mean > VOCAL_PITCH_SALIENCE_THRESHOLD
        and (from_t.spectral_centroid_hz or 0) > VOCAL_SPECTRAL_CENTROID_FLOOR_HZ
        and (to_t.spectral_centroid_hz or 0) > VOCAL_SPECTRAL_CENTROID_FLOOR_HZ
    )

    drum_conflict = False
    if (
        from_t.onset_rate is not None
        and to_t.onset_rate is not None
        and from_t.kick_prominence is not None
        and to_t.kick_prominence is not None
    ):
        onset_sim = 1.0 - min(abs(from_t.onset_rate - to_t.onset_rate) / 5.0, 1.0)
        kick_sim = 1.0 - min(abs(from_t.kick_prominence - to_t.kick_prominence) / 0.5, 1.0)
        drum_conflict = 0.5 * onset_sim + 0.5 * kick_sim < GROOVE_CONFLICT_THRESHOLD

    return ConstraintResult(vocal_conflict=vocal_conflict, drum_conflict=drum_conflict)


class TransitionScorer:
    """Compute transition quality between two tracks.

    Uses ``settings.*`` (via ``check_hard_constraints``) for hard reject
    thresholds and the supplied ``weights`` dict (or
    ``DEFAULT_TRANSITION_WEIGHTS``) for the weighted sum.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
    ) -> None:
        self.weights = weights or dict(DEFAULT_TRANSITION_WEIGHTS)

    def score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent: TransitionIntent | None = None,
        section_context: SectionContext | None = None,
    ) -> TransitionScore:
        """Compute the full 6-component score.

        Args:
            from_t: Features of the outgoing track.
            to_t: Features of the incoming track.
            intent: Optional context-aware intent for weight modifiers.
                When provided, per-intent weights override instance defaults.
            section_context: Optional structural context for the mix
                windows. When both sides are percussion-only sections,
                ``DRUM_ONLY_WEIGHT_OVERRIDE`` is used for the weighted
                sum and ``score_harmonic`` applies its drum-only floor.
                Drum-only override takes precedence over ``intent``.
        """
        result = check_hard_constraints(from_t, to_t)
        if result.rejection is not None:
            return result.rejection

        # Pick weight set: drum-only > intent override > instance default
        if section_context is not None and section_context.is_drum_only_pair:
            weights: dict[str, float] | None = DRUM_ONLY_WEIGHT_OVERRIDE
        elif intent is not None:
            weights = INTENT_WEIGHT_MODIFIERS[intent]
        else:
            weights = None

        return self._compute_score(
            from_t,
            to_t,
            weights=weights,
            section_context=section_context,
            vocal_conflict=result.vocal_conflict,
            drum_conflict=result.drum_conflict,
        )

    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
    ) -> TransitionScore:
        """Score a transition, reusing pre-computed candidate distances.

        When transition candidates are available, the BPM/key/energy
        distances have already been computed by ``CandidateService``.
        Skip recomputing them for hard-constraint checks.

        Falls back to a full ``score()`` if no candidate data is provided.
        """
        result = check_hard_constraints(
            from_t,
            to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
        )
        if result.rejection is not None:
            return result.rejection

        return self._compute_score(
            from_t,
            to_t,
            vocal_conflict=result.vocal_conflict,
            drum_conflict=result.drum_conflict,
        )

    # ── Shared internals ───────────────────────────

    def _compute_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        weights: dict[str, float] | None = None,
        section_context: SectionContext | None = None,
        *,
        vocal_conflict: bool = False,
        drum_conflict: bool = False,
    ) -> TransitionScore:
        """Run all 6 component functions and combine them with weights.

        Applies a multiplicative structure bonus (up to +8%) when section
        context shows a good structural pairing (e.g. outro→intro).
        """
        w = weights or self.weights
        bpm = score_bpm(from_t, to_t)
        harmonic = score_harmonic(from_t, to_t, section_context=section_context)
        energy = score_energy(from_t, to_t)
        spectral = score_spectral(from_t, to_t)
        groove = score_groove(from_t, to_t)
        timbral = score_timbral(from_t, to_t)

        overall = (
            w.get("bpm", 0) * bpm
            + w.get("harmonic", 0) * harmonic
            + w.get("energy", 0) * energy
            + w.get("spectral", 0) * spectral
            + w.get("groove", 0) * groove
            + w.get("timbral", 0) * timbral
        )

        overall *= _structure_bonus(section_context)

        return TransitionScore(
            bpm=bpm,
            harmonic=harmonic,
            energy=energy,
            spectral=spectral,
            groove=groove,
            timbral=timbral,
            overall=overall,
            vocal_conflict=vocal_conflict,
            drum_conflict=drum_conflict,
        )


# ── Structure bonus ──────────────────────────────

_MIX_OUT_QUALITY: dict[int, float] = {
    SectionType.OUTRO: 1.0,
    SectionType.BREAKDOWN: 0.85,
    SectionType.VALLEY: 0.7,
    SectionType.DROP: 0.5,
    SectionType.BUILD: 0.3,
    SectionType.INTRO: 0.1,
}

_MIX_IN_QUALITY: dict[int, float] = {
    SectionType.INTRO: 1.0,
    SectionType.DROP: 0.8,
    SectionType.BUILD: 0.7,
    SectionType.BREAKDOWN: 0.6,
    SectionType.VALLEY: 0.4,
    SectionType.OUTRO: 0.1,
}

_STRUCTURE_BONUS_MAX = 0.08


def _structure_bonus(section_context: SectionContext | None) -> float:
    """Multiplicative bonus for good structural pairings (1.0 - 1.08).

    Rewards transitions that happen at natural DJ mix points
    (e.g. outro→intro = 1.08, drop→intro = 0.94 * bonus).
    Returns 1.0 (neutral) when section data is unavailable.
    """
    if section_context is None:
        return 1.0
    if section_context.from_section is None or section_context.to_section is None:
        return 1.0
    out_q = _MIX_OUT_QUALITY.get(section_context.from_section, 0.3)
    in_q = _MIX_IN_QUALITY.get(section_context.to_section, 0.3)
    pair_quality = (out_q + in_q) / 2.0
    return 1.0 + _STRUCTURE_BONUS_MAX * (pair_quality - 0.5)
