"""TransitionScore dataclass — the result type of TransitionScorer.

Held in its own module so ``hard_constraints`` and other consumers can
import it without dragging the full scorer engine. The shape is part of
the public API; persisted DB rows from ``transitions`` are reconstructed
into TransitionScore instances by ``app/handlers/transition_persist``.

Field semantics (post Neural Mix refactor):

* ``bpm`` — tempo compatibility (BPM Gauss + stability + double/half).
* ``energy`` — LUFS energy-flow compatibility.
* ``harmonic`` — Neural Mix HARMONICS stem compatibility (key + Tonnetz +
  MFCC + spectral contrast). NB the column name kept its v0 semantic
  label "harmonic"; conceptually this is the harmonics stem from the
  djay Pro Neural Mix paradigm.
* ``spectral`` — Neural Mix BASS stem compatibility (Camelot + bass
  band energy + BPM). v0 column name kept; conceptually the bass stem.
* ``groove`` — Neural Mix DRUMS stem compatibility (BPM + kick
  prominence + onset rate + beat-loudness band cosine). v0 column name
  kept; conceptually the drums stem.
* ``timbral`` — Neural Mix VOCALS stem compatibility (centroid + chroma
  entropy + pitch salience). v0 column name kept; conceptually the
  vocals stem.

Future task (T6/T7) will rename the four stem fields/columns to
``drums``, ``bass``, ``harmonics``, ``vocals`` end-to-end. For now the
v0 names persist so the DB column rename can land as a separate atomic
migration without churning every consumer in this commit.

* ``overall`` — weighted sum of the six components.
* ``hard_reject`` — True iff a hard constraint (BPM > 10, Camelot ≥ 5,
  energy gap > 6 LUFS) was violated.
* ``reject_reason`` — human-readable rejection cause.
* ``best_transition`` — the Neural Mix preset the scorer believes fits
  best (argmax over the seven per-transition stem-weighted scores).
  Optional; ``None`` on hard reject. The picker (T3) returns the same
  value through a richer decision tree once context (sections, intent,
  subgenres) is in scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.transition.neural_mix import NeuralMixTransition


@dataclass
class TransitionScore:
    """Six-component transition score between two tracks (stem-aware)."""

    bpm: float = 0.0
    harmonic: float = 0.0
    energy: float = 0.0
    spectral: float = 0.0
    groove: float = 0.0
    timbral: float = 0.0
    overall: float = 0.0
    hard_reject: bool = False
    reject_reason: str | None = None
    best_transition: NeuralMixTransition | None = None
