"""Transition scoring engine — 6-component weighted formula.

Pure domain logic: no I/O, no DB, no async.
See docs/transition-scoring.md for full algorithm description.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.config import settings
from app.core.camelot import camelot_distance
from app.core.constants import DEFAULT_TRANSITION_WEIGHTS
from app.core.track_features import TrackFeatures
from app.core.transition_intent import INTENT_WEIGHT_MODIFIERS, TransitionIntent
from app.domain.transition.math_helpers import correlation, cosine_similarity


@dataclass
class TransitionScore:
    """6-component transition score between two tracks."""

    bpm: float = 0.0
    harmonic: float = 0.0
    energy: float = 0.0
    spectral: float = 0.0
    groove: float = 0.0
    timbral: float = 0.0
    overall: float = 0.0
    hard_reject: bool = False
    reject_reason: str | None = None


class TransitionScorer:
    """Compute transition quality between two tracks.

    Uses settings.* for hard reject thresholds and weights.
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
    ) -> TransitionScore:
        """Compute full 6-component score.

        Args:
            from_t: Features of the outgoing track.
            to_t: Features of the incoming track.
            intent: Optional context-aware intent for weight modifiers.
                When provided, per-intent weights override instance defaults.
        """
        rejection = self._check_hard_constraints(from_t, to_t)
        if rejection is not None:
            return rejection

        weights = INTENT_WEIGHT_MODIFIERS[intent] if intent is not None else None
        return self._compute_score(from_t, to_t, weights=weights)

    def score_with_candidates(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        candidate_bpm_distance: float | None = None,
        candidate_key_distance: int | None = None,
        candidate_energy_delta: float | None = None,
    ) -> TransitionScore:
        """Score a transition, reusing pre-computed candidate distances.

        When transition candidates are available, the BPM/key/energy distances
        have already been computed. This method skips re-computing them for
        hard-constraint checks, using the pre-computed values instead.

        Falls back to full score() if no candidate data provided.
        """
        rejection = self._check_hard_constraints(
            from_t,
            to_t,
            pre_bpm_dist=candidate_bpm_distance,
            pre_key_dist=candidate_key_distance,
            pre_energy_delta=candidate_energy_delta,
        )
        if rejection is not None:
            return rejection

        return self._compute_score(from_t, to_t)

    # ── Shared internals ───────────────────────────

    def _check_hard_constraints(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        pre_bpm_dist: float | None = None,
        pre_key_dist: int | None = None,
        pre_energy_delta: float | None = None,
    ) -> TransitionScore | None:
        """Check hard constraints; return a zero-score rejection or None if all pass."""
        from app.domain.transition.math_helpers import bpm_distance

        # ── BPM constraint ──
        if pre_bpm_dist is not None:
            bpm_diff: float | None = pre_bpm_dist
        elif from_t.bpm is not None and to_t.bpm is not None:
            bpm_diff = bpm_distance(from_t.bpm, to_t.bpm)
        else:
            bpm_diff = None

        if bpm_diff is not None and bpm_diff > settings.transition_hard_reject_bpm_diff:
            return TransitionScore(
                hard_reject=True,
                reject_reason=(
                    f"BPM diff {bpm_diff:.1f} > {settings.transition_hard_reject_bpm_diff}"
                ),
            )

        # ── Key constraint ──
        if pre_key_dist is not None:
            key_dist: int | None = pre_key_dist
        elif from_t.key_code is not None and to_t.key_code is not None:
            key_dist = camelot_distance(from_t.key_code, to_t.key_code)
        else:
            key_dist = None

        if key_dist is not None and key_dist >= settings.transition_hard_reject_camelot_dist:
            return TransitionScore(
                hard_reject=True,
                reject_reason=(
                    f"Camelot distance {key_dist} "
                    f">= {settings.transition_hard_reject_camelot_dist}"
                ),
            )

        # ── Energy constraint ──
        if pre_energy_delta is not None:
            energy_gap: float | None = pre_energy_delta
        elif from_t.integrated_lufs is not None and to_t.integrated_lufs is not None:
            energy_gap = abs(from_t.integrated_lufs - to_t.integrated_lufs)
        else:
            energy_gap = None

        if energy_gap is not None and energy_gap > settings.transition_hard_reject_energy_gap:
            return TransitionScore(
                hard_reject=True,
                reject_reason=(
                    f"Energy gap {energy_gap:.1f} LUFS "
                    f"> {settings.transition_hard_reject_energy_gap}"
                ),
            )

        return None

    def _compute_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        weights: dict[str, float] | None = None,
    ) -> TransitionScore:
        """Compute all 6 component scores and weighted overall."""
        w = weights or self.weights
        bpm = self._score_bpm(from_t, to_t)
        harmonic = self._score_harmonic(from_t, to_t)
        energy = self._score_energy(from_t, to_t)
        spectral = self._score_spectral(from_t, to_t)
        groove = self._score_groove(from_t, to_t)
        timbral = self._score_timbral(from_t, to_t)

        overall = (
            w.get("bpm", 0) * bpm
            + w.get("harmonic", 0) * harmonic
            + w.get("energy", 0) * energy
            + w.get("spectral", 0) * spectral
            + w.get("groove", 0) * groove
            + w.get("timbral", 0) * timbral
        )

        return TransitionScore(
            bpm=bpm,
            harmonic=harmonic,
            energy=energy,
            spectral=spectral,
            groove=groove,
            timbral=timbral,
            overall=overall,
        )

    # ── BPM ──────────────────────────────────────────

    def _score_bpm(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        from app.domain.transition.math_helpers import bpm_distance

        if from_t.bpm is None or to_t.bpm is None:
            return 0.5  # unknown = neutral
        delta = bpm_distance(from_t.bpm, to_t.bpm)
        sigma = 3.0  # ~3 BPM tolerance
        score = math.exp(-(delta**2) / (2 * sigma**2))

        # BPM stability factor: unstable tempo makes mixing harder
        if from_t.bpm_stability is not None and to_t.bpm_stability is not None:
            stability = min(from_t.bpm_stability, to_t.bpm_stability)
            score *= max(0.7, stability)  # up to 30% penalty for unstable BPM

        # BPM confidence factor: low confidence reduces score
        if from_t.bpm_confidence is not None and to_t.bpm_confidence is not None:
            min_conf = min(from_t.bpm_confidence, to_t.bpm_confidence)
            if min_conf < settings.scoring_bpm_confidence_floor:
                score *= max(0.7, min_conf / settings.scoring_bpm_confidence_floor)

        # Variable tempo penalty: hard to mix variable-tempo tracks
        if (from_t.variable_tempo is True) or (to_t.variable_tempo is True):
            score = max(0.0, score - settings.scoring_variable_tempo_penalty)

        return score

    # ── Harmonic ─────────────────────────────────────

    def _score_harmonic(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        if from_t.key_code is None or to_t.key_code is None:
            return 0.5
        dist = camelot_distance(from_t.key_code, to_t.key_code)
        base_scores = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
        base = base_scores.get(dist, 0.0)

        # Both atonal tracks → key less important, relax to at least 0.8
        if from_t.atonality is True and to_t.atonality is True:
            base = max(0.8, base)

        # Weight by HNR and chroma entropy
        hnr_factor = 1.0
        if from_t.hnr_db is not None and to_t.hnr_db is not None:
            avg_hnr = (from_t.hnr_db + to_t.hnr_db) / 2
            hnr_factor = max(0.5, min(1.0, (avg_hnr + 30) / 30))  # normalize -30..0 → 0.5..1.0

        score = base * hnr_factor

        # Tonnetz cosine similarity (30% weight when available)
        if from_t.tonnetz_vector and to_t.tonnetz_vector:
            tonnetz_cos = cosine_similarity(from_t.tonnetz_vector, to_t.tonnetz_vector)
            score = 0.70 * score + 0.30 * tonnetz_cos

        # Key confidence: low confidence → blend toward neutral (0.5)
        if from_t.key_confidence is not None and to_t.key_confidence is not None:
            min_conf = min(from_t.key_confidence, to_t.key_confidence)
            if min_conf < 0.5:
                blend = min_conf / 0.5  # 0.0 at conf=0, 1.0 at conf=0.5
                score = score * blend + 0.5 * (1.0 - blend)

        return score

    # ── Energy ───────────────────────────────────────

    def _score_energy(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        if from_t.integrated_lufs is None or to_t.integrated_lufs is None:
            return 0.5
        delta = to_t.integrated_lufs - from_t.integrated_lufs
        # Sigmoid centered at 0, slight preference for energy increase
        score = 1.0 / (1.0 + math.exp(-delta / 3.0))

        # LRA penalty: large loudness range difference = inconsistent dynamics
        if from_t.loudness_range_lu is not None and to_t.loudness_range_lu is not None:
            lra_diff = abs(from_t.loudness_range_lu - to_t.loudness_range_lu)
            if lra_diff > settings.scoring_lra_diff_penalty_threshold:
                score = max(0.0, score - settings.scoring_lra_diff_penalty)

        # Crest factor penalty: large difference = very different dynamics
        if from_t.crest_factor_db is not None and to_t.crest_factor_db is not None:
            crest_diff = abs(from_t.crest_factor_db - to_t.crest_factor_db)
            if crest_diff > settings.scoring_crest_diff_penalty_threshold:
                score = max(0.0, score - settings.scoring_crest_diff_penalty)

        # Energy slope bonus: same direction = coherent energy arc
        if (
            from_t.energy_slope is not None
            and to_t.energy_slope is not None
            and (from_t.energy_slope > 0) == (to_t.energy_slope > 0)
        ):
            score = min(1.0, score + settings.scoring_energy_slope_bonus)

        return score

    # ── Spectral ─────────────────────────────────────

    def _score_spectral(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        signals: list[float] = []
        weights: list[float] = []

        # MFCC cosine similarity (0.30)
        if from_t.mfcc_vector and to_t.mfcc_vector:
            signals.append(cosine_similarity(from_t.mfcc_vector, to_t.mfcc_vector))
            weights.append(0.30)

        # Centroid proximity (0.20)
        if from_t.spectral_centroid_hz is not None and to_t.spectral_centroid_hz is not None:
            max_c = max(from_t.spectral_centroid_hz, to_t.spectral_centroid_hz, 1.0)
            centroid_sim = max(
                0.0, 1.0 - abs(from_t.spectral_centroid_hz - to_t.spectral_centroid_hz) / max_c
            )
            signals.append(centroid_sim)
            weights.append(0.20)

        # Energy band balance (0.20)
        if from_t.energy_bands and to_t.energy_bands:
            signals.append(max(0.0, correlation(from_t.energy_bands, to_t.energy_bands)))
            weights.append(0.20)

        # Rolloff similarity: both rolloff points (0.15)
        rolloff_sims: list[float] = []
        if from_t.spectral_rolloff_85 is not None and to_t.spectral_rolloff_85 is not None:
            max_r = max(from_t.spectral_rolloff_85, to_t.spectral_rolloff_85, 1.0)
            rolloff_sims.append(
                max(0.0, 1.0 - abs(from_t.spectral_rolloff_85 - to_t.spectral_rolloff_85) / max_r)
            )
        if from_t.spectral_rolloff_95 is not None and to_t.spectral_rolloff_95 is not None:
            max_r = max(from_t.spectral_rolloff_95, to_t.spectral_rolloff_95, 1.0)
            rolloff_sims.append(
                max(0.0, 1.0 - abs(from_t.spectral_rolloff_95 - to_t.spectral_rolloff_95) / max_r)
            )
        if rolloff_sims:
            signals.append(sum(rolloff_sims) / len(rolloff_sims))
            weights.append(0.15)

        # Spectral slope similarity (0.10)
        if from_t.spectral_slope is not None and to_t.spectral_slope is not None:
            max_s = max(abs(from_t.spectral_slope), abs(to_t.spectral_slope), 1e-9)
            slope_sim = max(0.0, 1.0 - abs(from_t.spectral_slope - to_t.spectral_slope) / max_s)
            signals.append(slope_sim)
            weights.append(0.10)

        # Flux std similarity (0.05)
        if from_t.spectral_flux_std is not None and to_t.spectral_flux_std is not None:
            max_f = max(from_t.spectral_flux_std, to_t.spectral_flux_std, 1e-9)
            flux_sim = max(
                0.0, 1.0 - abs(from_t.spectral_flux_std - to_t.spectral_flux_std) / max_f
            )
            signals.append(flux_sim)
            weights.append(0.05)

        score = (
            sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)
            if weights
            else 0.5
        )

        # Dissonance penalty: two harsh tracks together = muddy mix
        if (
            from_t.dissonance_mean is not None
            and to_t.dissonance_mean is not None
            and from_t.dissonance_mean > 0.4
            and to_t.dissonance_mean > 0.4
        ):
            score = max(0.0, score - 0.15)

        # Spectral complexity penalty: two complex tracks = clutter
        if (
            from_t.spectral_complexity_mean is not None
            and to_t.spectral_complexity_mean is not None
        ) and abs(from_t.spectral_complexity_mean - to_t.spectral_complexity_mean) > 10:
            score = max(0.0, score - 0.10)

        return score

    # ── Groove ───────────────────────────────────────

    def _score_groove(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        signals: list[float] = []
        weights: list[float] = []

        # Onset rate similarity (0.25)
        if from_t.onset_rate is not None and to_t.onset_rate is not None:
            max_rate = max(from_t.onset_rate, to_t.onset_rate, 1.0)
            signals.append(max(0.0, 1.0 - abs(from_t.onset_rate - to_t.onset_rate) / max_rate))
            weights.append(0.25)

        # Kick prominence similarity (0.25)
        if from_t.kick_prominence is not None and to_t.kick_prominence is not None:
            signals.append(max(0.0, 1.0 - abs(from_t.kick_prominence - to_t.kick_prominence)))
            weights.append(0.25)

        # Beat loudness band ratio cosine (0.20)
        if from_t.beat_loudness_band_ratio and to_t.beat_loudness_band_ratio:
            signals.append(
                cosine_similarity(from_t.beat_loudness_band_ratio, to_t.beat_loudness_band_ratio)
            )
            weights.append(0.20)

        # Pulse clarity similarity (0.10)
        if from_t.pulse_clarity is not None and to_t.pulse_clarity is not None:
            signals.append(max(0.0, 1.0 - abs(from_t.pulse_clarity - to_t.pulse_clarity)))
            weights.append(0.10)

        # HP ratio similarity (0.10)
        if from_t.hp_ratio is not None and to_t.hp_ratio is not None:
            max_hp = max(from_t.hp_ratio, to_t.hp_ratio, 1e-9)
            signals.append(max(0.0, 1.0 - abs(from_t.hp_ratio - to_t.hp_ratio) / max_hp))
            weights.append(0.10)

        # Tempogram ratio vector cosine (0.10)
        if from_t.tempogram_ratio_vector and to_t.tempogram_ratio_vector:
            signals.append(
                cosine_similarity(from_t.tempogram_ratio_vector, to_t.tempogram_ratio_vector)
            )
            weights.append(0.10)

        if not weights:
            return 0.5

        return sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)

    # ── Timbral ──────────────────────────────────────

    def _score_timbral(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        """Timbral similarity: spectral contrast + pitch salience + danceability + dynamic complexity."""
        signals: list[float] = []
        weights: list[float] = []

        # Spectral contrast similarity (0.35)
        if from_t.spectral_contrast is not None and to_t.spectral_contrast is not None:
            diff = abs(from_t.spectral_contrast - to_t.spectral_contrast)
            signals.append(max(0.0, 1.0 - diff / 15.0))  # 15 dB = full penalty
            weights.append(0.35)

        # Pitch salience proximity (0.35)
        if from_t.pitch_salience_mean is not None and to_t.pitch_salience_mean is not None:
            diff = abs(from_t.pitch_salience_mean - to_t.pitch_salience_mean)
            signals.append(max(0.0, 1.0 - diff / 0.5))  # 0.5 = full penalty
            weights.append(0.35)

        # Danceability similarity (0.15): essentia unbounded, normalize over 3.0 range
        if from_t.danceability is not None and to_t.danceability is not None:
            max_d = max(abs(from_t.danceability), abs(to_t.danceability), 1e-9)
            diff = abs(from_t.danceability - to_t.danceability)
            signals.append(max(0.0, 1.0 - diff / max(max_d, 3.0)))
            weights.append(0.15)

        # Dynamic complexity similarity (0.15): range 0-~10
        if from_t.dynamic_complexity is not None and to_t.dynamic_complexity is not None:
            diff = abs(from_t.dynamic_complexity - to_t.dynamic_complexity)
            signals.append(max(0.0, 1.0 - diff / 10.0))
            weights.append(0.15)

        if not signals:
            return 0.5  # neutral when unavailable

        return sum(s * w for s, w in zip(signals, weights, strict=False)) / sum(weights)
