"""Transition scoring engine — 5-component weighted formula.

See docs/transition-scoring.md for full algorithm description.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.config import settings
from app.core.camelot import camelot_distance
from app.core.constants import DEFAULT_TRANSITION_WEIGHTS
from app.core.track_features import TrackFeatures as TrackFeatures  # re-export


@dataclass
class TransitionScore:
    """5-component transition score between two tracks."""

    bpm: float = 0.0
    harmonic: float = 0.0
    energy: float = 0.0
    spectral: float = 0.0
    groove: float = 0.0
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

    def score(self, from_t: TrackFeatures, to_t: TrackFeatures) -> TransitionScore:
        """Compute full 5-component score."""
        result = TransitionScore()

        # ── Hard constraints ─────────────────────────
        if from_t.bpm is not None and to_t.bpm is not None:
            bpm_diff = self._bpm_distance(from_t.bpm, to_t.bpm)
            if bpm_diff > settings.transition_hard_reject_bpm_diff:
                result.hard_reject = True
                result.reject_reason = (
                    f"BPM diff {bpm_diff:.1f} > {settings.transition_hard_reject_bpm_diff}"
                )
                return result

        if from_t.key_code is not None and to_t.key_code is not None:
            key_dist = camelot_distance(from_t.key_code, to_t.key_code)
            if key_dist >= settings.transition_hard_reject_camelot_dist:
                result.hard_reject = True
                result.reject_reason = f"Camelot distance {key_dist} >= {settings.transition_hard_reject_camelot_dist}"
                return result

        if from_t.integrated_lufs is not None and to_t.integrated_lufs is not None:
            energy_gap = abs(from_t.integrated_lufs - to_t.integrated_lufs)
            if energy_gap > settings.transition_hard_reject_energy_gap:
                result.hard_reject = True
                result.reject_reason = f"Energy gap {energy_gap:.1f} LUFS > {settings.transition_hard_reject_energy_gap}"
                return result

        # ── Component scores ─────────────────────────
        result.bpm = self._score_bpm(from_t, to_t)
        result.harmonic = self._score_harmonic(from_t, to_t)
        result.energy = self._score_energy(from_t, to_t)
        result.spectral = self._score_spectral(from_t, to_t)
        result.groove = self._score_groove(from_t, to_t)

        # ── Weighted overall ─────────────────────────
        result.overall = (
            self.weights["bpm"] * result.bpm
            + self.weights["harmonic"] * result.harmonic
            + self.weights["energy"] * result.energy
            + self.weights["spectral"] * result.spectral
            + self.weights["groove"] * result.groove
        )

        return result

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
        result = TransitionScore()

        # ── Hard constraints from pre-computed distances ──
        if candidate_bpm_distance is not None:
            if candidate_bpm_distance > settings.transition_hard_reject_bpm_diff:
                result.hard_reject = True
                result.reject_reason = (
                    f"BPM diff {candidate_bpm_distance:.1f} "
                    f"> {settings.transition_hard_reject_bpm_diff}"
                )
                return result
        elif from_t.bpm is not None and to_t.bpm is not None:
            bpm_diff = self._bpm_distance(from_t.bpm, to_t.bpm)
            if bpm_diff > settings.transition_hard_reject_bpm_diff:
                result.hard_reject = True
                result.reject_reason = (
                    f"BPM diff {bpm_diff:.1f} > {settings.transition_hard_reject_bpm_diff}"
                )
                return result

        if candidate_key_distance is not None:
            if candidate_key_distance >= settings.transition_hard_reject_camelot_dist:
                result.hard_reject = True
                result.reject_reason = (
                    f"Camelot distance {candidate_key_distance} "
                    f">= {settings.transition_hard_reject_camelot_dist}"
                )
                return result
        elif from_t.key_code is not None and to_t.key_code is not None:
            key_dist = camelot_distance(from_t.key_code, to_t.key_code)
            if key_dist >= settings.transition_hard_reject_camelot_dist:
                result.hard_reject = True
                result.reject_reason = (
                    f"Camelot distance {key_dist} "
                    f">= {settings.transition_hard_reject_camelot_dist}"
                )
                return result

        if candidate_energy_delta is not None:
            if candidate_energy_delta > settings.transition_hard_reject_energy_gap:
                result.hard_reject = True
                result.reject_reason = (
                    f"Energy gap {candidate_energy_delta:.1f} LUFS "
                    f"> {settings.transition_hard_reject_energy_gap}"
                )
                return result
        elif from_t.integrated_lufs is not None and to_t.integrated_lufs is not None:
            energy_gap = abs(from_t.integrated_lufs - to_t.integrated_lufs)
            if energy_gap > settings.transition_hard_reject_energy_gap:
                result.hard_reject = True
                result.reject_reason = (
                    f"Energy gap {energy_gap:.1f} LUFS "
                    f"> {settings.transition_hard_reject_energy_gap}"
                )
                return result

        # ── Component scores (same as score()) ────────
        result.bpm = self._score_bpm(from_t, to_t)
        result.harmonic = self._score_harmonic(from_t, to_t)
        result.energy = self._score_energy(from_t, to_t)
        result.spectral = self._score_spectral(from_t, to_t)
        result.groove = self._score_groove(from_t, to_t)

        # ── Weighted overall ──────────────────────────
        result.overall = (
            self.weights["bpm"] * result.bpm
            + self.weights["harmonic"] * result.harmonic
            + self.weights["energy"] * result.energy
            + self.weights["spectral"] * result.spectral
            + self.weights["groove"] * result.groove
        )

        return result

    # ── BPM ──────────────────────────────────────────

    @staticmethod
    def _bpm_distance(bpm_a: float, bpm_b: float) -> float:
        """Min distance considering double/half-time."""
        direct = abs(bpm_a - bpm_b)
        double = abs(bpm_a - bpm_b * 2)
        half = abs(bpm_a - bpm_b / 2)
        return min(direct, double, half)

    def _score_bpm(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        if from_t.bpm is None or to_t.bpm is None:
            return 0.5  # unknown = neutral
        delta = self._bpm_distance(from_t.bpm, to_t.bpm)
        sigma = 3.0  # ~3 BPM tolerance
        return math.exp(-(delta**2) / (2 * sigma**2))

    # ── Harmonic ─────────────────────────────────────

    def _score_harmonic(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        if from_t.key_code is None or to_t.key_code is None:
            return 0.5
        dist = camelot_distance(from_t.key_code, to_t.key_code)
        base_scores = {0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1}
        base = base_scores.get(dist, 0.0)

        # Weight by HNR and chroma entropy
        hnr_factor = 1.0
        if from_t.hnr_db is not None and to_t.hnr_db is not None:
            avg_hnr = (from_t.hnr_db + to_t.hnr_db) / 2
            hnr_factor = max(0.5, min(1.0, (avg_hnr + 30) / 30))  # normalize -30..0 → 0.5..1.0

        return base * hnr_factor

    # ── Energy ───────────────────────────────────────

    def _score_energy(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        if from_t.integrated_lufs is None or to_t.integrated_lufs is None:
            return 0.5
        delta = to_t.integrated_lufs - from_t.integrated_lufs
        # Sigmoid centered at 0, slight preference for energy increase
        return 1.0 / (1.0 + math.exp(-delta / 3.0))

    # ── Spectral ─────────────────────────────────────

    def _score_spectral(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        scores = []

        # MFCC cosine similarity
        if from_t.mfcc_vector and to_t.mfcc_vector:
            cos_sim = self._cosine_similarity(from_t.mfcc_vector, to_t.mfcc_vector)
            scores.append(cos_sim)

        # Centroid proximity
        if from_t.spectral_centroid_hz is not None and to_t.spectral_centroid_hz is not None:
            max_c = max(from_t.spectral_centroid_hz, to_t.spectral_centroid_hz, 1.0)
            centroid_sim = (
                1.0 - abs(from_t.spectral_centroid_hz - to_t.spectral_centroid_hz) / max_c
            )
            scores.append(max(0.0, centroid_sim))

        # Energy band balance
        if from_t.energy_bands and to_t.energy_bands:
            correlation = self._correlation(from_t.energy_bands, to_t.energy_bands)
            scores.append(max(0.0, correlation))

        return sum(scores) / len(scores) if scores else 0.5

    # ── Groove ───────────────────────────────────────

    def _score_groove(self, from_t: TrackFeatures, to_t: TrackFeatures) -> float:
        scores = []

        if from_t.onset_rate is not None and to_t.onset_rate is not None:
            max_rate = max(from_t.onset_rate, to_t.onset_rate, 1.0)
            onset_match = 1.0 - abs(from_t.onset_rate - to_t.onset_rate) / max_rate
            scores.append(max(0.0, onset_match))

        if from_t.kick_prominence is not None and to_t.kick_prominence is not None:
            kick_match = 1.0 - abs(from_t.kick_prominence - to_t.kick_prominence)
            scores.append(max(0.0, kick_match))

        return sum(scores) / len(scores) if scores else 0.5

    # ── Math helpers ─────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x**2 for x in a))
        norm_b = math.sqrt(sum(x**2 for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return max(0.0, min(1.0, (dot / (norm_a * norm_b) + 1) / 2))

    @staticmethod
    def _correlation(a: list[float], b: list[float]) -> float:
        n = len(a)
        if n == 0:
            return 0.0
        mean_a = sum(a) / n
        mean_b = sum(b) / n
        cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=False)) / n
        std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a) / n)
        std_b = math.sqrt(sum((y - mean_b) ** 2 for y in b) / n)
        if std_a == 0 or std_b == 0:
            return 0.0
        return cov / (std_a * std_b)
