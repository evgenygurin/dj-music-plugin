"""Neural Mix transition picker — context-aware decision tree.

The scorer (``app/domain/transition/scorer.py``) tells you *how
compatible* two tracks are. The picker tells you *which preset to play*
given that compatibility plus structural context (section labels,
subgenre pair, intent).

Decision tree (first match wins):

1. ``score.hard_reject`` → ECHO_OUT (rescue, masks the failure with
   echo tail).
2. Drum-only mix windows (both sides on intro/outro/sustain/ambient):
   ``score.drums > 0.85`` → DRUM_SWAP (groove-transfer);
   ``> 0.65`` → DRUM_CUT (drumless reset);
   else → FADE.
3. Vocal-active outro on A (3-signal proxy: ``pitch_salience_mean >
   0.55`` AND ``spectral_centroid_hz > 2200`` AND, when ``energy_bands``
   is available, ``(lowmid+mid) / total > 0.40``). See ``_vocal_active``
   for the full rationale.
   * Low-vocal B intro (``pitch_salience_mean < 0.3``) → VOCAL_SUSTAIN
   * High-vocal B intro → VOCAL_CUT
   * Missing B vocal data → ECHO_OUT (safe default).
4. Harmonic motif on A (low pitch salience, mid centroid, tonnetz
   present) + Camelot distance ≤ 1 + low-vocal B → HARMONIC_SUSTAIN.
5. High B-over-A energy delta (>2 LUFS) AND (intent=RAMP_UP OR
   subgenre_pair=HARD_PAIR) → DRUM_CUT (drop-style breakdown into
   slam).
5b. HYPNOTIC_PAIR AND ``enable_filter_sweep_style=True`` →
   FILTER_SWEEP (bass-forward high-pass filter sweep, signature
   hypnotic / minimal techno move).
6. Ambient pair OR intent=COOL_DOWN → FADE (gentle linear blend).
7. Default — **techno mixes on the drums**. This is the common case for
   instrumental 4/4 techno (no vocals, no melodic motif, no section
   context), and the right move is NOT an echo-tail. Route by drum-stem
   compatibility + energy direction:
   * ``score.drums >= 0.62`` and energy lifts (>+1.5 LUFS) → DRUM_CUT
     (drums lock, lift the energy with a quick swap / drop).
   * ``score.drums >= 0.62`` otherwise → DRUM_SWAP (the canonical techno
     move: long EQ-swap blend that trades A's drum bed for B's while
     bass / harmonic continuity carries the mix).
   * ``score.drums >= 0.45`` → DRUM_CUT (grooves only loosely lock — a
     cleaner quick swap beats a muddy blend).
   * else → ECHO_OUT (grooves don't lock at all — echo-tail rescue).

ECHO_OUT is therefore a **rescue**, not the blanket default. Before this
change every instrumental-techno pair without section/subgenre/intent
context fell through to ECHO_OUT, so whole sets came out 100 % echo_out.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.camelot.wheel import camelot_distance
from app.domain.transition.builders import build_recipe
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.neural_mix import NeuralMixTransition
from app.domain.transition.recipe import DEFAULT_TRANSITION_BARS, NeuralMixRecipe
from app.domain.transition.score import TransitionScore
from app.domain.transition.section_context import SectionContext
from app.domain.transition.subgenre_rules import SubgenrePairType, clamp_bars
from app.shared.features import TrackFeatures

# Lazy import to avoid circular deps at module level; resolved once on first call.
_SETTINGS_CACHE: object = None


def _filter_sweep_enabled() -> bool:
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is None:
        from app.config import get_settings

        _SETTINGS_CACHE = get_settings()
    return bool(
        getattr(getattr(_SETTINGS_CACHE, "transition", None), "enable_filter_sweep_style", True)
    )


# ── Picker decision thresholds ──────────────────────────────────────

_VOCAL_PRESENCE_PITCH_SALIENCE = 0.55
_VOCAL_PRESENCE_CENTROID_HZ = 2200.0
_VOCAL_LOW_PITCH_SALIENCE = 0.3
_VOCAL_PRESENCE_MIDBAND_RATIO = 0.40

_HARMONIC_MOTIF_MAX_PITCH_SALIENCE = 0.35
_HARMONIC_MOTIF_MIN_CENTROID_HZ = 800.0
_HARMONIC_MOTIF_MAX_CENTROID_HZ = 2400.0
_HARMONIC_KEY_DIST_MAX = 1

_ENERGY_DELTA_RAMP_UP_LUFS = 2.0

_DRUM_ONLY_DRUMS_HIGH = 0.85
_DRUM_ONLY_DRUMS_MID = 0.65

# Default drum-driven routing (rule 7). Techno is mixed on the drums, so
# DRUM_SWAP — not ECHO_OUT — is the canonical default when the drum stems
# lock. DRUM_CUT covers energy lifts and partial groove lock; ECHO_OUT is
# demoted to a groove-mismatch rescue only.
_DRUM_SWAP_FLOOR = 0.62
_DRUM_CUT_FLOOR = 0.45
_DRUM_CUT_ENERGY_LIFT_LUFS = 2.0


@dataclass(frozen=True)
class PickerDecision:
    """Output of ``pick_neural_mix``: which preset, why, and the rescue fallback."""

    transition: NeuralMixTransition
    confidence: float
    reason: str
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rescue: NeuralMixTransition = NeuralMixTransition.ECHO_OUT


# ── Helpers ─────────────────────────────────────────────────────────


def _vocal_active(t: TrackFeatures) -> bool:
    """Heuristic detection of vocal presence using up to 3 spectral proxies.

    A track is treated as "vocal-active" only when:

    1. ``pitch_salience_mean`` indicates sustained pitched content
       (threshold ``_VOCAL_PRESENCE_PITCH_SALIENCE``).
    2. ``spectral_centroid_hz`` lies in/above the vocal range
       (threshold ``_VOCAL_PRESENCE_CENTROID_HZ``).
    3. *If* per-band energies are available (``energy_bands`` populated with
       6 values), energy in the vocal frequency band
       (lowmid + mid = 300-3000 Hz, indices 2-3) accounts for at least
       ``_VOCAL_PRESENCE_MIDBAND_RATIO`` of total spectral energy.

    The third filter rejects acid-lead false-positives: TB-303-style
    resonant leads share signals (1)+(2) with vocals but concentrate
    their energy in highmid (3-7 kHz), not the formant band. When
    ``energy_bands`` is missing (legacy rows), we fall back to the
    2-signal check to avoid regressing older library entries.
    """
    if t.pitch_salience_mean is None or t.spectral_centroid_hz is None:
        return False
    if t.pitch_salience_mean <= _VOCAL_PRESENCE_PITCH_SALIENCE:
        return False
    if t.spectral_centroid_hz <= _VOCAL_PRESENCE_CENTROID_HZ:
        return False

    # Optional midband-ratio filter — only enforced when band data exists.
    if t.energy_bands is not None and len(t.energy_bands) >= 6:
        total = sum(t.energy_bands)
        if total > 1e-6:
            midband = t.energy_bands[2] + t.energy_bands[3]
            if midband / total < _VOCAL_PRESENCE_MIDBAND_RATIO:
                return False

    return True


def _vocal_low(t: TrackFeatures) -> bool:
    return t.pitch_salience_mean is not None and t.pitch_salience_mean < _VOCAL_LOW_PITCH_SALIENCE


def _vocal_data_missing(t: TrackFeatures) -> bool:
    return t.pitch_salience_mean is None or t.spectral_centroid_hz is None


def _harmonic_motif(t: TrackFeatures) -> bool:
    if t.pitch_salience_mean is None or t.spectral_centroid_hz is None:
        return False
    if not t.tonnetz_vector:
        return False
    return (
        t.pitch_salience_mean <= _HARMONIC_MOTIF_MAX_PITCH_SALIENCE
        and _HARMONIC_MOTIF_MIN_CENTROID_HZ
        <= t.spectral_centroid_hz
        <= _HARMONIC_MOTIF_MAX_CENTROID_HZ
    )


def _camelot_compatible(a: TrackFeatures, b: TrackFeatures) -> bool:
    if a.key_code is None or b.key_code is None:
        return False
    return camelot_distance(a.key_code, b.key_code) <= _HARMONIC_KEY_DIST_MAX


def _energy_delta_lufs(a: TrackFeatures, b: TrackFeatures) -> float | None:
    if a.integrated_lufs is None or b.integrated_lufs is None:
        return None
    return b.integrated_lufs - a.integrated_lufs


# ── Picker ──────────────────────────────────────────────────────────


def pick_neural_mix(
    score: TransitionScore,
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    section_context: SectionContext | None = None,
    subgenre_pair: SubgenrePairType | None = None,
    intent: TransitionIntent | None = None,
) -> PickerDecision:
    """Pick the best Neural Mix preset for an A→B transition.

    Returns a ``PickerDecision`` with the transition, picker confidence,
    a human-readable reason, optional warnings, and the rescue fallback.

    The decision tree (see module docstring) is first-match-wins; later
    rules only fire if earlier ones don't.
    """
    # 1. Hard reject.
    if score.hard_reject:
        return PickerDecision(
            transition=NeuralMixTransition.ECHO_OUT,
            confidence=0.55,
            reason=f"hard reject ({score.reject_reason or 'unknown'}) — echo-tail rescue",
            warnings=("hard reject — recipe is best-effort",),
        )

    # 2. Drum-only pair (both mix-out and mix-in on percussion-only sections).
    if section_context is not None and section_context.is_drum_only_pair:
        if score.drums > _DRUM_ONLY_DRUMS_HIGH:
            return PickerDecision(
                transition=NeuralMixTransition.DRUM_SWAP,
                confidence=0.92,
                reason=f"drum-only sections, drums={score.drums:.2f} — swap drum bed",
            )
        if score.drums > _DRUM_ONLY_DRUMS_MID:
            return PickerDecision(
                transition=NeuralMixTransition.DRUM_CUT,
                confidence=0.85,
                reason=f"drum-only sections, drums={score.drums:.2f} — drumless reset",
            )
        return PickerDecision(
            transition=NeuralMixTransition.FADE,
            confidence=0.70,
            reason=f"drum-only sections, drums={score.drums:.2f} too low — linear fade",
        )

    # 3. Vocal-active A outro.
    if _vocal_active(from_t):
        if _vocal_data_missing(to_t):
            return PickerDecision(
                transition=NeuralMixTransition.ECHO_OUT,
                confidence=0.65,
                reason="A vocal-active, B vocal data missing — echo-tail safe default",
                warnings=("incoming track missing vocal-presence proxy features",),
            )
        if _vocal_low(to_t):
            return PickerDecision(
                transition=NeuralMixTransition.VOCAL_SUSTAIN,
                confidence=0.88,
                reason="A vocal-active, B vocal-light — sustain A vocal over B inst",
            )
        return PickerDecision(
            transition=NeuralMixTransition.VOCAL_CUT,
            confidence=0.82,
            reason="A and B both vocal-active — cut A vocal to avoid clash",
            warnings=("two vocal lines — cut prevents stacking but timing must land",),
        )

    # 4. Harmonic motif on A + key compatible + low-vocal B.
    if _harmonic_motif(from_t) and _camelot_compatible(from_t, to_t) and _vocal_low(to_t):
        return PickerDecision(
            transition=NeuralMixTransition.HARMONIC_SUSTAIN,
            confidence=0.83,
            reason=("A harmonic motif, key compatible, B vocal-light — sustain A harmonic"),
        )

    # 5. High energy delta + ramp-up intent or hard subgenre pair → drop-style.
    delta = _energy_delta_lufs(from_t, to_t)
    if (
        delta is not None
        and delta > _ENERGY_DELTA_RAMP_UP_LUFS
        and (intent is TransitionIntent.RAMP_UP or subgenre_pair is SubgenrePairType.HARD_PAIR)
    ):
        return PickerDecision(
            transition=NeuralMixTransition.DRUM_CUT,
            confidence=0.86,
            reason=f"energy delta +{delta:.1f} LUFS into ramp-up — breakdown + slam",
        )

    # 5b. Hypnotic pair + filter sweep enabled — signature filter sweep.
    if subgenre_pair is SubgenrePairType.HYPNOTIC_PAIR and _filter_sweep_enabled():
        return PickerDecision(
            transition=NeuralMixTransition.FILTER_SWEEP,
            confidence=0.84,
            reason="hypnotic/minimal pair — bass-forward filter sweep",
        )

    # 6. Ambient pair OR cool-down intent → linear fade.
    if subgenre_pair is SubgenrePairType.AMBIENT_PAIR or intent is TransitionIntent.COOL_DOWN:
        return PickerDecision(
            transition=NeuralMixTransition.FADE,
            confidence=0.78,
            reason=(
                "ambient pair / cool-down intent — linear stem crossfade"
                if subgenre_pair is SubgenrePairType.AMBIENT_PAIR
                else "cool-down intent — linear stem crossfade"
            ),
        )

    # 7. Default — techno mixes on the drums. DRUM_SWAP is the canonical
    # move; DRUM_CUT for energy lifts / partial groove lock; ECHO_OUT only
    # when the grooves don't lock at all.
    if score.drums >= _DRUM_SWAP_FLOOR:
        if delta is not None and delta > _DRUM_CUT_ENERGY_LIFT_LUFS:
            return PickerDecision(
                transition=NeuralMixTransition.DRUM_CUT,
                confidence=0.80,
                reason=(
                    f"drums lock ({score.drums:.2f}), energy +{delta:.1f} LUFS — "
                    f"quick drum cut to lift"
                ),
            )
        return PickerDecision(
            transition=NeuralMixTransition.DRUM_SWAP,
            confidence=0.82,
            reason=f"drum-driven techno, drums={score.drums:.2f} — long EQ-swap blend",
        )
    if score.drums >= _DRUM_CUT_FLOOR:
        return PickerDecision(
            transition=NeuralMixTransition.DRUM_CUT,
            confidence=0.72,
            reason=f"grooves loosely lock (drums={score.drums:.2f}) — quick drum cut",
        )
    return PickerDecision(
        transition=NeuralMixTransition.ECHO_OUT,
        confidence=0.60,
        reason=f"groove mismatch (drums={score.drums:.2f}) — echo-tail rescue",
    )


# ── Recipe materialisation ──────────────────────────────────────────


def build_recipe_for_pair(
    score: TransitionScore,
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    section_context: SectionContext | None = None,
    subgenre_pair: SubgenrePairType | None = None,
    intent: TransitionIntent | None = None,
    bars: int = DEFAULT_TRANSITION_BARS,
) -> NeuralMixRecipe:
    """Pick a Neural Mix preset and materialise a full ``NeuralMixRecipe``.

    Convenience wrapper that runs the picker, scales the bar count via
    ``clamp_bars`` when a subgenre pair is supplied, and dispatches into
    the appropriate builder.
    """
    decision = pick_neural_mix(
        score,
        from_t,
        to_t,
        section_context=section_context,
        subgenre_pair=subgenre_pair,
        intent=intent,
    )
    effective_bars = clamp_bars(bars, subgenre_pair) if subgenre_pair is not None else bars
    return build_recipe(
        decision.transition,
        bars=effective_bars,
        mix_in_section=(
            section_context.to_section.name.lower()
            if section_context is not None and section_context.to_section is not None
            else None
        ),
        mix_out_section=(
            section_context.from_section.name.lower()
            if section_context is not None and section_context.from_section is not None
            else None
        ),
        confidence=decision.confidence,
        rescue=decision.rescue,
        explanation=decision.reason,
        warnings=decision.warnings,
    )


__all__ = [
    "PickerDecision",
    "build_recipe_for_pair",
    "pick_neural_mix",
]
