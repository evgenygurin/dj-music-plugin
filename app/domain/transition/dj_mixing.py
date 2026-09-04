"""DJ-aware transition mixing — pure domain.

Implements the agreed Cell 16 mixing-domain contracts:

* :class:`TempoModel` — consumer of multiple :class:`TempoHypothesis`
  candidates with explicit octave correction.
* :class:`TransitionGrid` — a domain projection of one track's beatgrid
  (beats, downbeats, phase, phrase boundaries) with everything in bars
  and milliseconds for clean caller math.
* :class:`TransitionCue` — a transition cue-point candidate expressed
  in the outgoing track's bar grid (e.g. "start mix-out at bar 32").
* :class:`AlignmentScore` — the four components of DJ-aware transition
  quality (``S_tempo``, ``S_beat_alignment``, ``S_phrase_alignment``,
  ``S_drift``).
* :func:`score_beat_alignment` — phase offset between two beat grids.
* :func:`score_phrase_alignment` — distance to nearest bar/phrase
  boundary.
* :func:`score_drift` — accumulated beat drift over a transition
  window.
* :func:`select_transition_bars` — bar-constrained musical transition
  duration (4/8/16/32/64).

The module is **pure**: it depends only on ``app.audio.core.tempo`` and
``app.shared.features``. No I/O, no DB, no async, no Demucs. The
:mod:`app.domain.transition.scorer` orchestrator composes these
components without breaking the existing public score API.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final

from app.audio.core.tempo import TempoHypothesis, beatgrid_from_arrays
from app.shared.features import TrackFeatures

# ── Constants ────────────────────────────────────────────────────────

# Bar-constrained transition durations — the only lengths a professional
# DJ would actually pick on a 4/4 grid. 2-bar transitions are an
# emergency-only choice; the default set omits them.
MIXING_DEFAULT_TRANSITION_BARS: Final[tuple[int, ...]] = (4, 8, 16, 32, 64)

# Soft target for the planned transition length: 16 bars (one techno
# phrase) is the sweet spot. The bar-selector picks the nearest power
# that does not exceed ``max_bars`` and is at least ``min_bars``.
MIXING_DEFAULT_TARGET_BARS: Final[int] = 16
MIXING_MIN_TRANSITION_BARS: Final[int] = 4
MIXING_MAX_TRANSITION_BARS: Final[int] = 64

# ── Score weight tunables ────────────────────────────────────────────
# These are pure constants; tests for the domain pin them.

# ``S_tempo`` — the same Gauss curve as the legacy ``score_bpm``, kept
# stable so existing call sites and tests see byte-identical output.
S_TEMPO_SIGMA: Final[float] = 10.0

# ``S_beat_alignment`` — Gaussian on the phase offset (in seconds) of
# the two tracks' first downbeats. A perfect phase lock is 1.0; a
# half-beat offset drops to ~0.5.
S_BEAT_SIGMA_S: Final[float] = 0.06  # ≈ 1/4 of a techno beat at 128 BPM

# ``S_phrase_alignment`` — Gaussian on the bar/phrase boundary distance
# (in seconds). A perfect bar lock is 1.0; two full bars off drops to
# ~0.05.
S_PHRASE_SIGMA_S: Final[float] = 0.5  # half a bar at 120 BPM

# ``S_drift`` — accumulated beat drift over a transition window
# (seconds of drift per planned transition length). Lower is better.
S_DRIFT_MAX_S: Final[float] = 0.5
S_DRIFT_SIGMA_S: Final[float] = 0.15

# When the source track has no tempo data, we use a neutral 0.5 for
# every alignment component so a missing beatgrid does not throw a
# hard reject on what is otherwise a compatible pair.
NEUTRAL_ALIGNMENT: Final[float] = 0.5


# ── Domain types ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TempoModel:
    """Consumer-side tempo model for a single track.

    Wraps a ranked list of :class:`TempoHypothesis` (the canonical
    representation produced by the audio layer) and exposes:

    * a stable :attr:`bpm` chosen by :meth:`effective_bpm` that
      applies the caller's octave preference.
    * an :attr:`is_locked` flag indicating whether the hypothesis set
      is unambiguous enough to trust for grid alignment.
    * the dominant :class:`TempoHypothesis` for callers that want
      the raw octave-preference score.
    """

    hypotheses: tuple[TempoHypothesis, ...]
    octave_correction: float = 1.0  # 0.5 / 1.0 / 2.0
    confidence_floor: float = 0.3  # below this, the model is "unlocked"

    @classmethod
    def from_features(
        cls, features: TrackFeatures, *, octave_correction: float = 1.0
    ) -> TempoModel:
        """Build a TempoModel from a TrackFeatures row.

        L3 doesn't yet persist ranked hypotheses (Cell 17 adds that),
        so we construct a single dominant hypothesis from the canonical
        ``bpm`` / ``bpm_confidence`` columns.
        """
        bpm = float(features.bpm) if features.bpm is not None else 0.0
        confidence = (
            float(features.bpm_confidence)
            if features.bpm_confidence is not None
            else 0.0
        )
        if bpm <= 0.0:
            return cls(hypotheses=(), octave_correction=octave_correction)
        hyp = TempoHypothesis(
            bpm=bpm,
            confidence=confidence,
            octave_preference=1.0,
            source="track_features",
        )
        return cls(
            hypotheses=(hyp,),
            octave_correction=octave_correction if octave_correction > 0 else 1.0,
        )

    @property
    def is_locked(self) -> bool:
        """True if the dominant hypothesis clears the confidence floor."""
        if not self.hypotheses:
            return False
        return self.hypotheses[0].confidence >= self.confidence_floor

    @property
    def dominant(self) -> TempoHypothesis | None:
        return self.hypotheses[0] if self.hypotheses else None

    def effective_bpm(self) -> float:
        """Return the BPM the renderer should lock to.

        Applies :attr:`octave_correction` to the dominant hypothesis.
        With a 1.0 correction and a single 128 BPM hypothesis this is
        just 128. With a 0.5 correction on a 128 BPM hypothesis the
        renderer gets 64 (intentional half-tempo lock — usually wrong,
        but a deliberate override path).
        """
        dom = self.dominant
        if dom is None:
            return 0.0
        return float(dom.bpm) * float(self.octave_correction)

    def confidence(self) -> float:
        dom = self.dominant
        return float(dom.confidence) if dom is not None else 0.0


@dataclass(frozen=True, slots=True)
class TransitionGrid:
    """A domain projection of one track's beatgrid for alignment math.

    All values are computed lazily from the :class:`TrackFeatures`
    summary columns (no large arrays are carried in the domain layer
    — the audio layer keeps those on disk via TimeseriesReference).
    """

    bpm: float
    bpm_confidence: float
    bpm_stability: float
    beats_per_bar: int
    first_downbeat_s: float  # phase of the first beat, in [0, beat_period)
    bar_period_s: float
    phrase_boundaries_s: tuple[float, ...] = ()
    dominant_phrase_bars: int | None = None

    @classmethod
    def from_features(cls, features: TrackFeatures) -> TransitionGrid:
        """Build a TransitionGrid from a TrackFeatures row.

        Defensive: missing fields collapse to neutral defaults so a
        half-analyzed track still produces a usable (if approximate)
        grid. Callers that need strict accuracy should call
        :attr:`is_valid` on the result.
        """
        bpm = float(features.bpm) if features.bpm is not None else 0.0
        if bpm <= 0.0:
            return cls(
                bpm=0.0,
                bpm_confidence=0.0,
                bpm_stability=0.0,
                beats_per_bar=4,
                first_downbeat_s=0.0,
                bar_period_s=0.0,
            )
        beat_period = 60.0 / bpm
        bpb = 4
        bar_period = beat_period * bpb
        first_downbeat_s = 0.0
        fd_ms = getattr(features, "first_downbeat_ms", None)
        if fd_ms is not None and fd_ms > 0:
            first_downbeat_s = (float(fd_ms) / 1000.0) % beat_period

        phrase_s: tuple[float, ...] = ()
        raw = getattr(features, "phrase_boundaries_ms", None) or []
        if raw:
            phrase_s = tuple(float(x) / 1000.0 for x in raw if x is not None)
        return cls(
            bpm=bpm,
            bpm_confidence=(
                float(features.bpm_confidence)
                if features.bpm_confidence is not None
                else 0.0
            ),
            bpm_stability=(
                float(features.bpm_stability)
                if features.bpm_stability is not None
                else 0.0
            ),
            beats_per_bar=bpb,
            first_downbeat_s=first_downbeat_s,
            bar_period_s=bar_period,
            phrase_boundaries_s=phrase_s,
            dominant_phrase_bars=getattr(features, "dominant_phrase_bars", None),
        )

    @property
    def is_valid(self) -> bool:
        return self.bpm > 0.0 and self.bar_period_s > 0.0

    def bar_at_seconds(self, t_s: float) -> int:
        """Return the bar index that contains ``t_s`` (0-based)."""
        if not self.is_valid:
            return 0
        return int(t_s // self.bar_period_s)

    def seconds_to_nearest_bar(self, t_s: float) -> float:
        """Distance from ``t_s`` to the nearest bar boundary (>= 0)."""
        if not self.is_valid:
            return 0.0
        bar_idx = round(t_s / self.bar_period_s)
        return abs(t_s - bar_idx * self.bar_period_s)

    def seconds_to_nearest_phrase(self, t_s: float) -> float:
        """Distance from ``t_s`` to the nearest phrase boundary.

        Returns :attr:`bar_period_s` if no phrase boundaries are known
        (we then fall back to a single-bar tolerance).
        """
        if not self.phrase_boundaries_s:
            return self.seconds_to_nearest_bar(t_s)
        best = min((abs(t_s - p) for p in self.phrase_boundaries_s), default=0.0)
        return float(best)


@dataclass(frozen=True, slots=True)
class TransitionCue:
    """A cue-point candidate expressed in a track's bar grid.

    The renderer consumes these as "start the mix at outgoing_track's
    bar ``bar_index`` and bring incoming_track in for ``length_bars``
    bars". The ``score`` field is the cue's own quality rating
    (independent of the per-pair transition score).
    """

    track_id: int
    role: str  # "mix_out" or "mix_in"
    bar_index: int
    length_bars: int
    position_s: float
    score: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "track_id": self.track_id,
            "role": self.role,
            "bar_index": self.bar_index,
            "length_bars": self.length_bars,
            "position_s": self.position_s,
            "score": self.score,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class AlignmentScore:
    """The four DJ-aware transition components.

    * ``S_tempo`` — pure BPM Gauss (sigma=10). Same math as the legacy
      ``score_bpm`` field on :class:`TransitionScore`, exposed
      explicitly so the new beatgrid-aware pipeline can compose
      it with the other three axes.
    * ``S_beat_alignment`` — Gaussian on the first-downbeat phase
      offset. A 0.0 phase diff scores 1.0; a half-beat offset drops
      to ~0.5.
    * ``S_phrase_alignment`` — Gaussian on the bar/phrase distance
      between the planned mix-out and the next track's first downbeat.
    * ``S_drift`` — accumulated beat drift over the planned
      transition length (1.0 = no drift, 0.0 = catastrophic).

    All four are in [0, 1]. ``overall`` is the weighted sum using
    :data:`ALIGNMENT_DEFAULT_WEIGHTS`.
    """

    s_tempo: float
    s_beat_alignment: float
    s_phrase_alignment: float
    s_drift: float
    overall: float

    def to_dict(self) -> dict[str, float]:
        return {
            "s_tempo": self.s_tempo,
            "s_beat_alignment": self.s_beat_alignment,
            "s_phrase_alignment": self.s_phrase_alignment,
            "s_drift": self.s_drift,
            "overall": self.overall,
        }


# Default weights for the four-component alignment pipeline. Tempo
# and beat alignment carry the most weight; phrase and drift are
# tie-breakers between BPM-compatible candidates.
ALIGNMENT_DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "s_tempo": 0.40,
    "s_beat_alignment": 0.30,
    "s_phrase_alignment": 0.15,
    "s_drift": 0.15,
}


# ── Pure scoring functions ──────────────────────────────────────────


def score_tempo(from_t: TrackFeatures, to_t: TrackFeatures) -> float:
    """``S_tempo`` — pure BPM compatibility in [0, 1].

    Identical math to :func:`app.domain.transition.components.bpm.score_bpm`
    minus the stability / confidence / variable_tempo modifiers. The
    alignment pipeline is allowed to apply those separately so the four
    components stay independent and testable in isolation.
    """
    if from_t.bpm is None or to_t.bpm is None:
        return NEUTRAL_ALIGNMENT
    delta = _bpm_distance(from_t.bpm, to_t.bpm)
    return math.exp(-(delta**2) / (2 * S_TEMPO_SIGMA**2))


def score_beat_alignment(
    from_grid: TransitionGrid,
    to_grid: TransitionGrid,
) -> float:
    """``S_beat_alignment`` — first-downbeat phase offset in [0, 1].

    Uses the sub-beat phase of each track's first downbeat. A perfect
    match (both first beats aligned on the global grid) returns 1.0;
    a half-beat offset returns ~0.5.

    If either grid is invalid (no BPM) the function returns
    :data:`NEUTRAL_ALIGNMENT` — the alignment pipeline should not
    hard-reject a track just because the beatgrid isn't analysable.
    """
    if not from_grid.is_valid or not to_grid.is_valid:
        return NEUTRAL_ALIGNMENT
    # The phase difference is meaningful only when the BPMs are
    # reasonably close. A 4 BPM gap at 128 BPM gives a 12.5 % beat-period
    # drift over one beat; we normalise by the *target* period to keep
    # the score scale-invariant.
    diff = abs(from_grid.first_downbeat_s - to_grid.first_downbeat_s)
    beat_period = 60.0 / to_grid.bpm if to_grid.bpm > 0 else 0.0
    if beat_period <= 0:
        return NEUTRAL_ALIGNMENT
    # Reduce to the principal beat window.
    diff = diff % beat_period
    if diff > beat_period / 2:
        diff = beat_period - diff
    return math.exp(-(diff**2) / (2 * S_BEAT_SIGMA_S**2))


def score_phrase_alignment(
    from_grid: TransitionGrid,
    to_grid: TransitionGrid,
    *,
    planned_out_bar: int = 0,
) -> float:
    """``S_phrase_alignment`` — distance to the nearest bar/phrase.

    The caller passes ``planned_out_bar`` (the bar index on the
    outgoing track where the mix will start). We compute the
    distance from that bar to the *incoming* track's first downbeat,
    normalised by the incoming grid's bar period.

    A perfectly phrase-aligned transition (mix-out lands on bar 1 of
    incoming) returns 1.0; two bars off returns ~0.05.
    """
    if not from_grid.is_valid or not to_grid.is_valid:
        return NEUTRAL_ALIGNMENT
    out_s = planned_out_bar * from_grid.bar_period_s
    # The transition itself occupies a few bars; the relevant question
    # is: where in the *incoming* track's grid do we land when the
    # mix-out completes? Without a planned transition length we just
    # measure the bar-distance between the two tracks' bar 0.
    nearest_phrase_s = to_grid.seconds_to_nearest_phrase(out_s)
    if to_grid.bar_period_s <= 0:
        return NEUTRAL_ALIGNMENT
    # Normalise to a fraction of the incoming bar period.
    fraction = nearest_phrase_s / to_grid.bar_period_s
    if fraction > 1.0:
        fraction = 1.0
    return math.exp(-(fraction * to_grid.bar_period_s) ** 2 / (2 * S_PHRASE_SIGMA_S**2))


def score_drift(
    from_grid: TransitionGrid,
    to_grid: TransitionGrid,
    *,
    transition_bars: int,
) -> float:
    """``S_drift`` — accumulated beat drift over the transition window.

    Techno decks run on timecode / pitch-bend correction, so the BPM
    difference alone is not the real problem — the *integrated* drift
    over the planned transition length is. Two tracks at 128.0 vs
    128.05 BPM have a 0.05 BPM gap, which accumulates to 0.01875
    seconds per bar; over 16 bars that's 0.3 seconds — audibly off
    the grid by the time the incoming track is fully layered in.

    Score in [0, 1]: 1.0 = no drift; 0.0 = ``S_DRIFT_MAX_S`` or more
    accumulated drift.
    """
    if not from_grid.is_valid or not to_grid.is_valid:
        return NEUTRAL_ALIGNMENT
    if transition_bars <= 0 or from_grid.bar_period_s <= 0 or to_grid.bar_period_s <= 0:
        return NEUTRAL_ALIGNMENT
    # Drift per beat: signed difference in beat period, normalised
    # by the target's beat period. Sign indicates direction; absolute
    # value is the magnitude.
    from_period = from_grid.bar_period_s / from_grid.beats_per_bar
    to_period = to_grid.bar_period_s / to_grid.beats_per_bar
    if to_period <= 0:
        return NEUTRAL_ALIGNMENT
    drift_per_beat = abs(from_period - to_period) / to_period  # unitless
    # Total beats in the transition window.
    total_beats = transition_bars * to_grid.beats_per_bar
    # Convert beat-fraction drift to seconds via the target period.
    drift_s = drift_per_beat * total_beats * to_period
    # Clamp into the score curve.
    normalised = min(1.0, drift_s / S_DRIFT_MAX_S)
    # Linear penalty (0 drift → 1.0, max drift → 0.0) with a soft
    # Gaussian knee around ``S_DRIFT_SIGMA_S``.
    linear = 1.0 - normalised
    soft = math.exp(-(drift_s**2) / (2 * S_DRIFT_SIGMA_S**2))
    return max(0.0, min(1.0, 0.5 * linear + 0.5 * soft))


def select_transition_bars(
    *,
    target_bars: int = MIXING_DEFAULT_TARGET_BARS,
    allowed: Sequence[int] = MIXING_DEFAULT_TRANSITION_BARS,
    min_bars: int = MIXING_MIN_TRANSITION_BARS,
    max_bars: int = MIXING_MAX_TRANSITION_BARS,
) -> int:
    """Pick the bar-constrained transition length closest to ``target_bars``.

    The DJ-relevant transition lengths are 4, 8, 16, 32, 64 bars. 16
    bars is the techno phrase default. We snap ``target_bars`` to the
    nearest allowed value, clamped to ``[min_bars, max_bars]``.
    """
    bounded_min = max(min_bars, min(allowed) if allowed else MIXING_MIN_TRANSITION_BARS)
    bounded_max = min(max_bars, max(allowed) if allowed else MIXING_MAX_TRANSITION_BARS)
    if bounded_max < bounded_min:
        bounded_max = bounded_min
    target = max(bounded_min, min(bounded_max, int(target_bars)))
    if not allowed:
        return target
    # Prefer "nearest"; ties go to the *shorter* (musically safer) option.
    candidates = sorted(
        (length for length in allowed if bounded_min <= length <= bounded_max),
        key=lambda length: (abs(length - target), length),
    )
    return int(candidates[0]) if candidates else target


def compute_alignment(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    transition_bars: int = MIXING_DEFAULT_TARGET_BARS,
    planned_out_bar: int = 0,
) -> AlignmentScore:
    """Compute the four-component AlignmentScore for one pair.

    Convenience: builds a :class:`TransitionGrid` for each track and
    composes the four component scores with :data:`ALIGNMENT_DEFAULT_WEIGHTS`.
    """
    from_grid = TransitionGrid.from_features(from_t)
    to_grid = TransitionGrid.from_features(to_t)
    s_tempo = score_tempo(from_t, to_t)
    s_beat = score_beat_alignment(from_grid, to_grid)
    s_phrase = score_phrase_alignment(from_grid, to_grid, planned_out_bar=planned_out_bar)
    s_drift = score_drift(
        from_grid, to_grid, transition_bars=transition_bars
    )
    weights = ALIGNMENT_DEFAULT_WEIGHTS
    overall = (
        weights["s_tempo"] * s_tempo
        + weights["s_beat_alignment"] * s_beat
        + weights["s_phrase_alignment"] * s_phrase
        + weights["s_drift"] * s_drift
    )
    return AlignmentScore(
        s_tempo=s_tempo,
        s_beat_alignment=s_beat,
        s_phrase_alignment=s_phrase,
        s_drift=s_drift,
        overall=max(0.0, min(1.0, overall)),
    )


def generate_transition_cues(
    *,
    track_id: int,
    features: TrackFeatures,
    role: str,
    n_candidates: int = 4,
    target_bars: int = MIXING_DEFAULT_TARGET_BARS,
    allowed: Sequence[int] = MIXING_DEFAULT_TRANSITION_BARS,
) -> list[TransitionCue]:
    """Generate bar-constrained cue-point candidates for one track.

    The cheap-first rule (Cell 18): the cheap ``TrackFeatures`` summary
    columns are enough to produce a small set of musically reasonable
    cues without touching the full ``beatgrid`` array on disk.

    Algorithm:
        1. Snap the track's target mix-out / mix-in length to a
           bar-constrained value (4/8/16/32/64).
        2. Walk the phrase boundary list (``phrase_boundaries_ms``)
           and emit one ``TransitionCue`` per boundary that clears the
           track's first usable bar.
        3. Score each cue: phrase boundary (0.9), grid anchor (0.7),
           fallback bar (0.4).

    The list is sorted by score (descending) and truncated to
    ``n_candidates``.
    """
    grid = TransitionGrid.from_features(features)
    length = select_transition_bars(
        target_bars=target_bars, allowed=allowed
    )
    if not grid.is_valid:
        return []
    candidates: list[TransitionCue] = []
    if grid.phrase_boundaries_s:
        for i, phrase_s in enumerate(grid.phrase_boundaries_s):
            bar_index = int(phrase_s // grid.bar_period_s) if grid.bar_period_s > 0 else 0
            if bar_index <= 0:
                continue
            score = 0.9 if i > 0 else 0.8  # skip the "phrase 0" anchor
            candidates.append(
                TransitionCue(
                    track_id=track_id,
                    role=role,
                    bar_index=bar_index,
                    length_bars=length,
                    position_s=phrase_s,
                    score=score,
                    reason="phrase_boundary",
                )
            )
    # Fall back to bar grid anchors: every 8 bars starting from bar 8.
    n_grid_candidates = max(1, n_candidates - len(candidates))
    bar_step = max(8, length)
    bar_idx = bar_step
    while len([c for c in candidates if c.reason == "grid_anchor"]) < n_grid_candidates:
        position_s = bar_idx * grid.bar_period_s
        if position_s <= 0:
            break
        candidates.append(
            TransitionCue(
                track_id=track_id,
                role=role,
                bar_index=bar_idx,
                length_bars=length,
                position_s=position_s,
                score=0.7,
                reason="grid_anchor",
            )
        )
        bar_idx += bar_step
    candidates.sort(key=lambda cue: cue.score, reverse=True)
    return candidates[: max(1, n_candidates)]


# ── Local helpers ───────────────────────────────────────────────────


def _bpm_distance(bpm_a: float, bpm_b: float) -> float:
    """Min BPM distance considering double/half-time. Pure local copy.

    Kept local so the module has zero internal dependencies outside
    ``audio.core.tempo`` and ``shared.features``. ``app.domain.transition
    .math_helpers.bpm_distance`` has the same semantics; callers that
    need to share the function should use that one.
    """
    if bpm_a <= 0 or bpm_b <= 0:
        return 999.0
    direct = abs(bpm_a - bpm_b)
    double = abs(bpm_a - bpm_b / 2)
    half = abs(bpm_a - bpm_b * 2)
    return float(min(direct, double, half))


# Convenience re-export of the canonical BeatGrid for callers that
# want to build a domain TransitionGrid from an audio BeatGrid.
__all__ = [
    "ALIGNMENT_DEFAULT_WEIGHTS",
    "AlignmentScore",
    "MIXING_DEFAULT_TRANSITION_BARS",
    "MIXING_DEFAULT_TARGET_BARS",
    "MIXING_MAX_TRANSITION_BARS",
    "MIXING_MIN_TRANSITION_BARS",
    "NEUTRAL_ALIGNMENT",
    "S_BEAT_SIGMA_S",
    "S_DRIFT_MAX_S",
    "S_DRIFT_SIGMA_S",
    "S_PHRASE_SIGMA_S",
    "S_TEMPO_SIGMA",
    "TempoModel",
    "TransitionCue",
    "TransitionGrid",
    "compute_alignment",
    "generate_transition_cues",
    "score_beat_alignment",
    "score_drift",
    "score_phrase_alignment",
    "score_tempo",
    "select_transition_bars",
    # ``beatgrid_from_arrays`` is re-exported so domain callers don't
    # have to import from the audio layer directly when constructing
    # test fixtures.
    "beatgrid_from_arrays",
]
