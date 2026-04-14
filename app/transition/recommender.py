"""TransitionRecommender — selects the best djay Pro AI Neural Mix FX.

Priority-based rules map audio features to one of 7 Neural Mix Crossfader FX
presets. djay Pro AI handles all stem automation automatically — we only
decide *which* preset to use.

Priority order (first matching rule wins):
  1. DRUM_CUT     — both tracks drum-heavy, hard section cut
  2. DRUM_SWAP    — swap drum stem at the phrase boundary
  3. HARMONIC_SUSTAIN — sustain harmonics/pads over new groove
  4. VOCAL_SUSTAIN    — hold outgoing vocal over incoming instrumental
  5. VOCAL_CUT        — clear vocal spectrum before bringing B in
  6. ECHO_OUT         — echo tail on energy drop or gap
  7. FADE             — default smooth crossfade
"""

from __future__ import annotations

from app.core.constants import NeuralMixCrossfaderFX
from app.entities.audio.features import TrackFeatures
from app.transition.constants import (
    VOCAL_PITCH_SALIENCE_THRESHOLD,
    VOCAL_SPECTRAL_CENTROID_FLOOR_HZ,
)
from app.transition.models import SectionContext, TransitionRecommendation, TransitionScore

# ── Thresholds (no magic numbers in rule logic) ──────────────────────────────

_KICK_HEAVY = 0.6  # kick_prominence above this → drum-heavy track
_HNR_MELODIC = 8.0  # HNR dB above this → melodic/harmonic-rich track
_HP_MELODIC = 0.6  # hp_ratio above this → harmonic-rich
_HP_PERCUSSIVE = 0.35  # hp_ratio below this → percussive-dominant
_ENERGY_GAP_LUFS = 2.0  # LUFS delta triggering echo-out
_CONFIDENCE_HIGH = 0.90
_CONFIDENCE_MED = 0.80
_CONFIDENCE_LOW = 0.70
_CONFIDENCE_FALLBACK = 0.60


def _kick(f: TrackFeatures) -> float:
    return f.kick_prominence or 0.0


def _hnr(f: TrackFeatures) -> float:
    return f.hnr_db or 0.0


def _hp(f: TrackFeatures) -> float:
    return f.hp_ratio or 0.5


def _lufs(f: TrackFeatures) -> float:
    return f.integrated_lufs or -14.0


def _pitch_salience(f: TrackFeatures) -> float:
    return f.pitch_salience_mean or 0.0


def _centroid(f: TrackFeatures) -> float:
    return f.spectral_centroid_hz or 0.0


def _has_vocals(f: TrackFeatures) -> bool:
    return (
        _pitch_salience(f) > VOCAL_PITCH_SALIENCE_THRESHOLD
        and _centroid(f) > VOCAL_SPECTRAL_CENTROID_FLOOR_HZ
    )


class TransitionRecommender:
    """Select the optimal djay Pro AI Neural Mix Crossfader FX for a pair.

    Usage::

        rec = TransitionRecommender()
        result = rec.recommend(score, features_a, features_b)
        # result.fx_type → NeuralMixCrossfaderFX value to use in djay Pro AI
    """

    def recommend(
        self,
        score: TransitionScore,
        features_a: TrackFeatures,
        features_b: TrackFeatures,
        *,
        section_context: SectionContext | None = None,
    ) -> TransitionRecommendation:
        """Return the best Neural Mix FX recommendation for this transition.

        Hard-rejected transitions default to FADE at low confidence.
        """
        if score.hard_reject:
            return TransitionRecommendation(
                fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_FADE,
                confidence=_CONFIDENCE_FALLBACK,
                reason=score.reject_reason or "hard reject",
                alt_fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_ECHO_OUT,
            )

        return (
            self._try_drum_cut(score, features_a, features_b, section_context)
            or self._try_drum_swap(score, features_a, features_b)
            or self._try_harmonic_sustain(score, features_a, features_b)
            or self._try_vocal_sustain(score, features_a, features_b)
            or self._try_vocal_cut(score, features_a, features_b)
            or self._try_echo_out(score, features_a, features_b)
            or self._fade(score)
        )

    # ── Priority rules ───────────────────────────────────────────────────────

    def _try_drum_cut(
        self,
        score: TransitionScore,
        fa: TrackFeatures,
        fb: TrackFeatures,
        ctx: SectionContext | None,
    ) -> TransitionRecommendation | None:
        """DRUM_CUT: both tracks drum-heavy → hard cut on the phrase boundary."""
        both_drum_heavy = _kick(fa) > _KICK_HEAVY and _kick(fb) > _KICK_HEAVY
        drum_only = ctx.is_drum_only_pair if ctx else False
        if both_drum_heavy or drum_only:
            return TransitionRecommendation(
                fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT,
                confidence=_CONFIDENCE_HIGH,
                reason="both tracks drum-heavy — hard cut on phrase boundary",
                alt_fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP,
            )
        return None

    def _try_drum_swap(
        self,
        score: TransitionScore,
        fa: TrackFeatures,
        fb: TrackFeatures,
    ) -> TransitionRecommendation | None:
        """DRUM_SWAP: swap drum stem when B is drum-heavy and groove is compatible."""
        if _kick(fb) > _KICK_HEAVY and score.groove > 0.55 and score.bpm > 0.70:
            return TransitionRecommendation(
                fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP,
                confidence=_CONFIDENCE_MED,
                reason="B is drum-heavy — swap drum stem at phrase boundary",
                alt_fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_FADE,
            )
        return None

    def _try_harmonic_sustain(
        self,
        score: TransitionScore,
        fa: TrackFeatures,
        fb: TrackFeatures,
    ) -> TransitionRecommendation | None:
        """HARMONIC_SUSTAIN: both melodic/harmonic-rich and keys are compatible."""
        both_melodic = _hnr(fa) > _HNR_MELODIC and _hp(fa) > _HP_MELODIC
        compatible_keys = score.harmonic > 0.55
        if both_melodic and compatible_keys:
            return TransitionRecommendation(
                fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_HARMONIC_SUSTAIN,
                confidence=_CONFIDENCE_MED,
                reason="both tracks melodic — sustain harmonics across transition",
                alt_fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_FADE,
            )
        return None

    def _try_vocal_sustain(
        self,
        score: TransitionScore,
        fa: TrackFeatures,
        fb: TrackFeatures,
    ) -> TransitionRecommendation | None:
        """VOCAL_SUSTAIN: A has vocals, B is more instrumental."""
        a_has_vocals = _has_vocals(fa)
        b_is_instrumental = not _has_vocals(fb) or _hp(fb) > _HP_MELODIC
        if a_has_vocals and b_is_instrumental:
            return TransitionRecommendation(
                fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_VOCAL_SUSTAIN,
                confidence=_CONFIDENCE_MED,
                reason="A has vocals — hold vocal stem over incoming groove",
                alt_fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_HARMONIC_SUSTAIN,
            )
        return None

    def _try_vocal_cut(
        self,
        score: TransitionScore,
        fa: TrackFeatures,
        fb: TrackFeatures,
    ) -> TransitionRecommendation | None:
        """VOCAL_CUT: both tracks have vocals — cut A's vocals to clear headroom."""
        if _has_vocals(fa) and _has_vocals(fb):
            return TransitionRecommendation(
                fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_VOCAL_CUT,
                confidence=_CONFIDENCE_MED,
                reason="both tracks have vocals — cut A vocals to prevent clash",
                alt_fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_FADE,
            )
        return None

    def _try_echo_out(
        self,
        score: TransitionScore,
        fa: TrackFeatures,
        fb: TrackFeatures,
    ) -> TransitionRecommendation | None:
        """ECHO_OUT: energy drop or large energy gap between tracks."""
        energy_gap = abs(_lufs(fa) - _lufs(fb))
        a_louder = _lufs(fa) > _lufs(fb)
        if score.energy < 0.45 or (a_louder and energy_gap > _ENERGY_GAP_LUFS):
            return TransitionRecommendation(
                fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_ECHO_OUT,
                confidence=_CONFIDENCE_LOW,
                reason=f"energy gap {energy_gap:.1f} LUFS — echo tail on outgoing",
                alt_fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_FADE,
            )
        return None

    def _fade(self, score: TransitionScore) -> TransitionRecommendation:
        """FADE: default smooth crossfade when no specific rule matches."""
        return TransitionRecommendation(
            fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_FADE,
            confidence=_CONFIDENCE_LOW,
            reason="smooth crossfade — default",
        )
