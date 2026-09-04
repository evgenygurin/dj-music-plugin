"""BeatGrid analyzer — first-class beatgrid representation in the audio layer.

The :class:`BeatGridAnalyzer` upgrades the BPM/beat analyzers from "one
BPM float" to a first-class beatgrid:

* BPM expressed as a ranked list of :class:`TempoHypothesis` candidates
  with explicit 0.5x/1x/2x ambiguity scoring.
* Beat timestamps + downbeats + bar boundaries derived from the
  dominant hypothesis.
* Sub-beat phase of the first beat (renderer grid anchor).
* Per-bar tempo curve (local drift signal).
* Phrase boundary timestamps.
* Reuses the shared onset envelope from ``AnalysisContext`` — no extra
  librosa/essentia dependency is introduced.

The analyzer is registered at L3 (SCORING) so it ships with the
standard pipeline call without re-tiering BPM/beat. The existing
``bpm`` and ``beat`` analyzers are NOT modified — their features
remain the canonical DB columns. ``beatgrid`` adds a richer
representation on top, kept cheap enough to run on every track.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np

from app.audio.analyzers.base import BaseAnalyzer, register_analyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.rhythm import (
    find_beat_times,
    sample_interpolated,
    tempo_from_onset_autocorrelation,
)
from app.audio.core.tempo import (
    TempoHypothesis,
    beatgrid_from_arrays,
    derive_phrase_boundaries,
    downbeats_from_beats,
    phase_from_first_beat,
    resolve_octave,
    tempo_curve_from_beat_times,
)

# BPM ambiguity lattice: candidate ratios to evaluate against the raw
# autocorrelation peak. Half / double are the common techno pitfalls;
# we explicitly avoid evaluating every integer multiple of the peak
# because that produces a flood of meaningless near-zero confidences.
_BPM_HYPOTHESIS_RATIOS: tuple[float, ...] = (0.5, 1.0, 2.0)


# Re-export the core constructor under the analyzer module name so
# legacy callers importing ``build_beatgrid`` from the analyzer still
# work after the move to ``core.tempo``.
build_beatgrid = beatgrid_from_arrays


@register_analyzer
class BeatGridAnalyzer(BaseAnalyzer):
    """Produce a first-class :class:`BeatGrid` from the shared onset envelope.

    Determinism: every output is a deterministic function of the
    supplied :class:`AnalysisContext`. No random sources, no time
    sources. The same audio + same frame parameters → identical
    beatgrid on every run.
    """

    name: ClassVar[str] = "beatgrid"
    level: ClassVar[int] = 3
    capabilities: ClassVar[frozenset[str]] = frozenset({"tempo", "rhythm", "beat"})
    required_packages: ClassVar[list[str]] = ["librosa"]
    depends_on: ClassVar[frozenset[str]] = frozenset({"bpm"})
    # Reuses the same 60s clip as the BPM analyzer — the 3-window
    # stitched clip is representative for stable techno BPM. The
    # beatgrid inherits the BPM confidence / stability values from
    # the prior phase, so we don't need the full track here.
    clip_duration_s: ClassVar[float | None] = 60.0

    def _extract(
        self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Compute a beatgrid from the shared onset envelope.

        ``prior_results`` carries the BPM analyzer output when this
        analyzer is dispatched in the dependent phase. We use it as a
        ``preferred_bpm`` hint for octave disambiguation so the new
        beatgrid stays consistent with the canonical BPM column.
        """
        prior = prior_results or {}
        prior_bpm = prior.get("bpm")
        preferred_bpm = float(prior_bpm) if isinstance(prior_bpm, (int, float)) else None

        sr = ctx.sr
        hop_length = ctx.params.hop_length
        onset_env = ctx.get_onset_env()

        estimate = tempo_from_onset_autocorrelation(onset_env, sr, hop_length)
        hypotheses = _build_tempo_hypotheses(onset_env, sr, hop_length, estimate)

        if not hypotheses:
            empty = beatgrid_from_arrays(
                bpm=0.0,
                bpm_confidence=0.0,
                bpm_stability=0.0,
                variable_tempo=False,
                beats_per_bar=4,
                beat_times_s=(),
                downbeat_times_s=(),
                bar_times_s=(),
                phase_s=0.0,
                hypotheses=(),
                tempo_curve=(),
                phrase_boundaries_s=(),
            )
            return {
                "beatgrid": empty.to_dict(),
                "tempo_hypotheses": [],
            }

        dominant = resolve_octave(hypotheses, preferred_bpm=preferred_bpm)
        bpm = dominant.bpm
        confidence = dominant.confidence

        # Beat times — anchored on the dominant hypothesis. Use a
        # generous max_bpm so half-tempo candidates still produce
        # some peaks (the renderer can pick the on-grid ones).
        target_bpm = max(bpm, 110.0)
        beat_times = find_beat_times(onset_env, sr, hop_length, bpm_hint=target_bpm, max_bpm=240.0)

        # Inherit stability from the BPM analyzer when present — it
        # already runs the median-IBI outlier filter and is the
        # canonical source of truth. Fall back to a local recompute
        # when the prior phase is missing (e.g. running beatgrid in
        # isolation via the registry).
        if "bpm_stability" in prior and "variable_tempo" in prior:
            stability = float(prior["bpm_stability"])
            variable_tempo = bool(prior["variable_tempo"])
        else:
            from app.audio.analyzers.bpm import compute_tempo_stability

            stability, variable_tempo = compute_tempo_stability(beat_times)

        beats_per_bar = 4  # techno default; meter analyzer refines it
        downbeats, bars = downbeats_from_beats(beat_times.tolist(), beats_per_bar)
        beat_period = 60.0 / bpm if bpm > 0 else 0.0
        phase = phase_from_first_beat(beat_times.tolist(), beat_period)
        tempo_curve = tempo_curve_from_beat_times(
            beat_times.tolist(), beats_per_bar=beats_per_bar, window_bars=4
        )
        phrase_boundaries = derive_phrase_boundaries([float(t) for t in bars], min_phrase_bars=8)

        grid = beatgrid_from_arrays(
            bpm=bpm,
            bpm_confidence=confidence,
            bpm_stability=stability,
            variable_tempo=variable_tempo,
            beats_per_bar=beats_per_bar,
            beat_times_s=tuple(float(t) for t in beat_times),
            downbeat_times_s=downbeats,
            bar_times_s=bars,
            phase_s=phase,
            hypotheses=tuple(hypotheses),
            tempo_curve=tempo_curve,
            phrase_boundaries_s=phrase_boundaries,
        )

        return {
            "beatgrid": grid.to_dict(),
            "tempo_hypotheses": [
                {
                    "bpm": round(h.bpm, 4),
                    "confidence": round(h.confidence, 4),
                    "octave_preference": round(h.octave_preference, 4),
                    "source": h.source,
                }
                for h in hypotheses
            ],
        }


def _build_tempo_hypotheses(
    onset_env: np.ndarray,
    sr: int,
    hop_length: int,
    estimate: Any,
) -> list[TempoHypothesis]:
    """Score 0.5x / 1x / 2x BPM candidates around the autocorrelation peak.

    For each ratio, sample the autocorrelation at the corresponding
    lag, then convert to BPM. The ``octave_preference`` score is the
    ratio's share of the sum across the three candidates — values
    near 1.0 mean the 1x hypothesis dominates; values near 0.0 mean
    the autocorrelation is ambiguous and an external caller may
    want to override the 1x default.
    """
    if estimate.bpm <= 0 or len(estimate.autocorrelation) < 4:
        return []

    acf = estimate.autocorrelation
    acf_max = float(np.max(acf)) if float(np.max(acf)) > 0 else 1.0
    acf_norm = acf / acf_max

    frames_per_sec = sr / hop_length
    base_lag = estimate.lag_frames
    if base_lag <= 0:
        return []

    candidates: list[tuple[float, float, float]] = []  # (ratio, bpm, normalized_value)
    for ratio in _BPM_HYPOTHESIS_RATIOS:
        target_lag = base_lag / ratio if ratio > 0 else base_lag
        value = sample_interpolated(acf_norm, target_lag)
        if ratio <= 0:
            continue
        bpm = 60.0 * frames_per_sec / target_lag
        if not (40.0 <= bpm <= 480.0):
            continue
        candidates.append((ratio, bpm, float(np.clip(value, 0.0, 1.0))))

    if not candidates:
        return [
            TempoHypothesis(
                bpm=estimate.bpm,
                confidence=estimate.confidence,
                octave_preference=1.0,
            )
        ]

    # Normalize across the three candidates so they sum to 1.0.
    total = sum(c[2] for c in candidates) or 1.0
    hypotheses: list[TempoHypothesis] = []
    for ratio, bpm, value in candidates:
        preference = value / total
        hypotheses.append(
            TempoHypothesis(
                bpm=bpm,
                confidence=float(np.clip(value, 0.0, 1.0)),
                octave_preference=float(np.clip(preference, 0.0, 1.0)),
                source=f"autocorrelation:{ratio:g}x",
            )
        )

    # Sort by confidence so the dominant hypothesis leads the list.
    hypotheses.sort(key=lambda h: h.confidence, reverse=True)
    return hypotheses


__all__ = [
    "BeatGridAnalyzer",
    "beatgrid_from_arrays",
    "build_beatgrid",
]
