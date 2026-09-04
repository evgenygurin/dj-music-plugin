"""Core tempo / beatgrid types — pure dataclasses, numpy-only.

The audio analysis layer exposes tempo as a *hypothesis distribution*
not a single BPM float, so callers can resolve 0.5x/1x/2x ambiguity
explicitly. The :class:`BeatGrid` aggregates the dominant hypothesis
into a concrete timeline: beat timestamps, downbeats, phase, bars,
phrase boundaries, and a tempo curve (per-bar BPM).

This module is intentionally I/O-free and free of librosa — it's the
canonical data shape used by every layer (analyzers, render, MCP
resources, domain models). Determinism rules:

* No mutable shared state.
* No ``time.time`` / random sources.
* All numerics derived from the inputs given.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

# Octave-equivalence ratios considered when scoring a BPM hypothesis.
# 0.5x / 1x / 2x is the common techno ambiguity; we also include 3x/4x
# because half-tempo false-positives cascade from 3x into 1.5x into
# 0.75x when the onset envelope has strong off-beat transients.
_OCTAVE_RATIOS: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0, 4.0)


@dataclass(frozen=True, slots=True)
class TempoHypothesis:
    """One candidate BPM with confidence and a 0.5x/1x/2x ambiguity score.

    ``bpm`` is the raw candidate. ``octave_preference`` is a relative
    weighting in ``[0, 1]`` saying how strongly this hypothesis prefers
    the 1x octave interpretation over the octave-halved/doubled ones.
    It is intentionally NOT a probability — a downstream consumer may
    decide that 80 BPM is really a 160 BPM track (kick on every beat)
    and override the choice.
    """

    bpm: float
    confidence: float
    octave_preference: float
    source: str = "autocorrelation"

    def octave_variants(self) -> list[tuple[float, float]]:
        """Yield (multiplier, bpm) pairs over the standard octave ratios.

        The returned list always contains the 1x variant. Used to walk
        the BPM lattice when comparing against a target tempo.
        """
        return [(r, self.bpm * r) for r in _OCTAVE_RATIOS]


@dataclass(frozen=True, slots=True)
class TempoCurvePoint:
    """One point on the per-bar tempo curve.

    ``bpm`` is the local tempo estimate at the center of the bar
    starting at ``t_s``; ``confidence`` is the strength of the
    autocorrelation peak used to derive it.
    """

    t_s: float
    bpm: float
    confidence: float


@dataclass(frozen=True, slots=True)
class BeatGrid:
    """First-class beatgrid representation.

    Fields
    ------
    bpm
        Dominant tempo (BPM). The ``dominant`` field on the
        :class:`TempoCurvePoint` may report small local deviations
        but ``bpm`` is the single best estimate for the track.
    bpm_confidence
        ``[0, 1]`` confidence in the dominant hypothesis.
    bpm_stability
        ``[0, 1]`` — 1.0 means every inter-beat interval is identical
        to the median; 0.0 means the IBI coefficient of variation is
        >= 0.5.
    variable_tempo
        True when local tempo drift exceeds the techno threshold.
    beats_per_bar
        Beats per bar (4 for 4/4, 3 for 3/4). 4 by default.
    beat_times_s
        Beat timestamps in seconds, aligned to the local tempo
        hypothesis. Always ``>= 2`` entries; the renderer relies on
        ``beat_times_s[0]`` as the on-grid anchor.
    downbeat_times_s
        Bar-1 beat timestamps (one per bar, ``beats_per_bar`` beats
        apart). Length is ``len(beat_times_s) // beats_per_bar``.
    bar_times_s
        Bar start timestamps. ``bar_times_s[i] == downbeat_times_s[i]``
        — both lists are exposed for caller convenience.
    phase_s
        Sub-beat offset of the first beat relative to ``t=0``. In
        ``[0, beat_period)``. Used by the render engine to align the
        kick transient against the global mix grid.
    tempo_curve
        Per-bar local BPM. Empty when only one bar was analysable.
    hypotheses
        Ranked list of BPM candidates the analyzer considered. The
        first entry is the dominant hypothesis; the rest explain the
        0.5x/1x/2x ambiguity if the caller wants to disambiguate.
    phrase_boundaries_s
        Optional phrase boundary timestamps in seconds. Empty if
        the input was too short to derive a phrase structure.
    """

    bpm: float
    bpm_confidence: float
    bpm_stability: float
    variable_tempo: bool
    beats_per_bar: int
    beat_times_s: tuple[float, ...]
    downbeat_times_s: tuple[float, ...]
    bar_times_s: tuple[float, ...]
    phase_s: float
    tempo_curve: tuple[TempoCurvePoint, ...] = field(default_factory=tuple)
    hypotheses: tuple[TempoHypothesis, ...] = field(default_factory=tuple)
    phrase_boundaries_s: tuple[float, ...] = field(default_factory=tuple)

    @property
    def beat_period_s(self) -> float:
        """Period of one beat in seconds, derived from ``bpm``."""
        if self.bpm <= 0:
            return 0.0
        return 60.0 / self.bpm

    @property
    def bar_period_s(self) -> float:
        """Period of one bar in seconds (``beats_per_bar * beat_period``)."""
        return self.beat_period_s * max(1, self.beats_per_bar)

    @property
    def n_bars(self) -> int:
        return len(self.bar_times_s)

    @property
    def n_beats(self) -> int:
        return len(self.beat_times_s)

    def first_beat_s(self) -> float:
        """Anchor beat timestamp in seconds (0.0 when no beats)."""
        return self.beat_times_s[0] if self.beat_times_s else 0.0

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly representation (lists, not tuples)."""
        return {
            "bpm": round(self.bpm, 4),
            "bpm_confidence": round(self.bpm_confidence, 4),
            "bpm_stability": round(self.bpm_stability, 4),
            "variable_tempo": self.variable_tempo,
            "beats_per_bar": self.beats_per_bar,
            "beat_times_s": [round(t, 6) for t in self.beat_times_s],
            "downbeat_times_s": [round(t, 6) for t in self.downbeat_times_s],
            "bar_times_s": [round(t, 6) for t in self.bar_times_s],
            "phase_s": round(self.phase_s, 6),
            "tempo_curve": [
                {
                    "t_s": round(p.t_s, 6),
                    "bpm": round(p.bpm, 4),
                    "confidence": round(p.confidence, 4),
                }
                for p in self.tempo_curve
            ],
            "hypotheses": [
                {
                    "bpm": round(h.bpm, 4),
                    "confidence": round(h.confidence, 4),
                    "octave_preference": round(h.octave_preference, 4),
                    "source": h.source,
                }
                for h in self.hypotheses
            ],
            "phrase_boundaries_s": [round(t, 6) for t in self.phrase_boundaries_s],
        }


def resolve_octave(
    hypotheses: Sequence[TempoHypothesis],
    *,
    preferred_bpm: float | None = None,
) -> TempoHypothesis:
    """Pick the hypothesis that best matches the octave-preference rule.

    Algorithm:
        1. Filter to the cluster of hypotheses within 5% of the
           maximum ``confidence`` — they all explain the same
           autocorrelation peak.
        2. If ``preferred_bpm`` is set, prefer the hypothesis whose
           ``bpm * r`` is closest to ``preferred_bpm`` for any
           ``r in (0.5, 1, 2)``.
        3. Otherwise, prefer the 1x hypothesis; break ties by
           ``octave_preference * confidence``.

    Returns the dominant hypothesis (always the first entry in
    ``hypotheses``) when the input is empty.
    """
    if not hypotheses:
        return TempoHypothesis(0.0, 0.0, 0.0, source="empty")
    if len(hypotheses) == 1:
        return hypotheses[0]

    if preferred_bpm is not None and preferred_bpm > 0:
        best = min(
            hypotheses,
            key=lambda h: abs(h.bpm - preferred_bpm),
        )
        return best

    # The source analyzer has already labelled every candidate's preference.
    # Do not assume list position means "1x": candidates are ranked by ACF
    # strength and a half/double peak may be stronger than the nominal one.
    return max(hypotheses, key=lambda h: h.octave_preference * h.confidence)


def downbeats_from_beats(
    beat_times_s: Sequence[float],
    beats_per_bar: int,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Split a beat sequence into (downbeats, bars).

    Returns two tuples of equal length — one downbeat per bar. The
    renderer treats the first downbeat as the global bar-1 anchor.

    With fewer than ``beats_per_bar`` beats, both tuples are empty.
    """
    if beats_per_bar < 1:
        beats_per_bar = 4
    if len(beat_times_s) < beats_per_bar:
        return (), ()
    n_bars = len(beat_times_s) // beats_per_bar
    indices = list(range(0, n_bars * beats_per_bar, beats_per_bar))
    # Once the grid has established two complete bars, retain an exact final
    # bar-boundary beat as an anchor even when the following bar is clipped.
    # This matters for short 3/4 excerpts used by the meter analyzer.
    if n_bars >= 2 and len(beat_times_s) % beats_per_bar == 1:
        indices.append(n_bars * beats_per_bar)
    downbeats = tuple(float(beat_times_s[index]) for index in indices)
    return downbeats, downbeats


def phase_from_first_beat(
    beat_times_s: Sequence[float],
    beat_period_s: float,
) -> float:
    """Sub-beat offset of the first beat relative to ``t=0``.

    In ``[0, beat_period_s)``. Returns 0.0 on degenerate input.
    """
    if not beat_times_s or beat_period_s <= 0:
        return 0.0
    first = float(beat_times_s[0])
    if first < 0:
        first = first % beat_period_s
    return first % beat_period_s


def tempo_curve_from_beat_times(
    beat_times_s: Sequence[float],
    *,
    beats_per_bar: int,
    window_bars: int = 4,
) -> tuple[TempoCurvePoint, ...]:
    """Estimate local BPM in a sliding window of ``window_bars`` bars.

    The local BPM is the median inter-beat interval inside the window,
    converted to BPM. Empty input → empty curve. A single window
    covering the whole beat sequence yields a one-element curve.
    """
    if beats_per_bar < 1 or len(beat_times_s) < 2 * beats_per_bar:
        return ()
    window = max(1, window_bars) * beats_per_bar
    if window < 2:
        return ()

    beats_arr = np.asarray(beat_times_s, dtype=np.float64)
    points: list[TempoCurvePoint] = []
    n = len(beats_arr)
    step = max(1, window // 2)
    for start in range(0, n - window + 1, step):
        end = start + window
        ibis = np.diff(beats_arr[start:end])
        ibis = ibis[ibis > 0]
        if len(ibis) < 2:
            continue
        med = float(np.median(ibis))
        if med <= 0:
            continue
        bpm = 60.0 / med
        # Window-level confidence: 1 - normalized MAD. Bounded in [0, 1].
        mad = float(np.median(np.abs(ibis - med)))
        confidence = max(0.0, min(1.0, 1.0 - (mad / med) * 4.0))
        t_center = float(beats_arr[start + window // 2])
        points.append(TempoCurvePoint(t_s=t_center, bpm=bpm, confidence=confidence))

    if not points:
        return ()
    # Always include the full-track median as a final anchor point so
    # callers can use the last point as a reliable summary statistic.
    full_ibis = np.diff(beats_arr)
    full_ibis = full_ibis[full_ibis > 0]
    if len(full_ibis) >= 2:
        med = float(np.median(full_ibis))
        if med > 0:
            bpm = 60.0 / med
            mad = float(np.median(np.abs(full_ibis - med)))
            confidence = max(0.0, min(1.0, 1.0 - (mad / med) * 4.0))
            t_center = float(beats_arr[len(beats_arr) // 2])
            if not points or abs(points[-1].t_s - t_center) > 1e-6:
                points.append(TempoCurvePoint(t_s=t_center, bpm=bpm, confidence=confidence))
    return tuple(points)


def derive_phrase_boundaries(
    bar_times_s: Sequence[float],
    *,
    min_phrase_bars: int = 8,
) -> tuple[float, ...]:
    """Snap-spaced phrase boundaries from bar times.

    Techno phrases are typically 8, 16, or 32 bars. We pick the
    smallest divisor of ``len(bar_times_s)`` that is >= ``min_phrase_bars``
    and at most 32, so a 64-bar track yields boundaries every 8 bars
    while a 24-bar excerpt yields boundaries every 8 bars too.

    Returns an empty tuple when there are fewer than ``min_phrase_bars``
    bars.
    """
    if len(bar_times_s) < min_phrase_bars:
        return ()
    n_bars = len(bar_times_s)
    for size in (8, 16, 32):
        if n_bars >= size and n_bars % size == 0:
            step = size
            break
    else:
        step = min_phrase_bars
    indices = list(range(0, n_bars, step))
    if indices[-1] != n_bars - 1:
        indices.append(n_bars - 1)
    return tuple(float(bar_times_s[i]) for i in indices)


def is_multiple_of_bpm(
    candidate: float,
    reference: float,
    *,
    tolerance_bpm: float = 0.5,
) -> bool:
    """Check whether ``candidate`` is an integer multiple of ``reference``.

    Helper used by hypothesis resolution: a 240 BPM hypothesis is
    only a 2x of 120 BPM if they line up within ``tolerance_bpm``.
    """
    if reference <= 0 or candidate <= 0:
        return False
    for ratio in (candidate / reference, reference / candidate):
        nearest = round(ratio)
        if nearest >= 1 and abs(ratio - nearest) * min(candidate, reference) <= tolerance_bpm:
            return True
    return False


def round_bpm(bpm: float, *, step: float = 0.01) -> float:
    """Round BPM to a stable step for serialization.

    The default 0.01 step keeps the JSON output short while preserving
    the parabolic-interpolation precision of the autocorrelation
    analyzer.
    """
    if not math.isfinite(bpm):
        return 0.0
    return round(round(bpm / step) * step, 4)


def beatgrid_from_arrays(
    *,
    bpm: float,
    bpm_confidence: float,
    bpm_stability: float,
    variable_tempo: bool,
    beats_per_bar: int,
    beat_times_s: tuple[float, ...],
    downbeat_times_s: tuple[float, ...],
    bar_times_s: tuple[float, ...],
    phase_s: float,
    hypotheses: tuple[TempoHypothesis, ...] = (),
    tempo_curve: tuple[TempoCurvePoint, ...] = (),
    phrase_boundaries_s: tuple[float, ...] = (),
) -> BeatGrid:
    """Construct a :class:`BeatGrid` with the obvious invariants applied.

    Public helper used by analyzers, render code, and tests. Lives in
    ``core`` so non-audio layers (domain, MCP resources) can fabricate
    grids without importing the analyzer module.
    """
    if beats_per_bar < 1:
        beats_per_bar = 4
    confidence = max(0.0, min(1.0, float(bpm_confidence)))
    stability = max(0.0, min(1.0, float(bpm_stability)))
    return BeatGrid(
        bpm=float(bpm),
        bpm_confidence=confidence,
        bpm_stability=stability,
        variable_tempo=bool(variable_tempo),
        beats_per_bar=int(beats_per_bar),
        beat_times_s=tuple(float(t) for t in beat_times_s),
        downbeat_times_s=tuple(float(t) for t in downbeat_times_s),
        bar_times_s=tuple(float(t) for t in bar_times_s),
        phase_s=max(0.0, float(phase_s)),
        tempo_curve=tuple(tempo_curve),
        hypotheses=tuple(hypotheses),
        phrase_boundaries_s=tuple(float(t) for t in phrase_boundaries_s),
    )
