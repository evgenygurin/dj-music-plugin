"""TransitionScore dataclass — the result type of TransitionScorer.

Held in its own module so ``hard_constraints`` and other consumers can
import it without dragging the full scorer engine. The shape is part of
the public API; persisted DB rows from ``transitions`` are reconstructed
into TransitionScore instances by ``app/handlers/transition_persist``.

Field semantics (Neural Mix paradigm, v1.3.1):

* ``bpm`` — tempo compatibility (BPM Gauss + stability + double/half).
* ``energy`` — LUFS energy-flow compatibility.
* ``drums`` — Neural Mix DRUMS stem compatibility (BPM lock + kick
  prominence + onset rate + beat-loudness band cosine).
* ``bass`` — Neural Mix BASS stem compatibility (Camelot wheel + bass
  band energy + BPM Gauss).
* ``harmonics`` — Neural Mix HARMONICS stem compatibility (Camelot +
  Tonnetz + MFCC + spectral contrast; HNR-weighted).
* ``vocals`` — Neural Mix VOCALS stem compatibility (spectral centroid
  + chroma entropy + pitch salience proxies).

Pre-v1.3.1 field names were ``harmonic`` / ``spectral`` / ``groove`` /
``timbral`` — semantic but no longer descriptive after the Neural Mix
refactor reused them as stem compats. The v1.3.1 rename brings field,
DB column, and weights-dict labels in sync with the stem they hold.

* ``overall`` — weighted sum of the six components.
* ``hard_reject`` — True iff a hard constraint (BPM > 10, Camelot ≥ 5,
  energy gap > 6 LUFS) was violated.
* ``reject_reason`` — human-readable rejection cause.
* ``best_transition`` — the Neural Mix preset the scorer believes fits
  best (argmax over the seven per-transition stem-weighted scores).
* ``section_pair_class`` — populated when scoring with a
  ``SectionContext``; one of ``SectionPairClass`` enum string values
  ("drum_only" / "drop_to_drop" / "breakdown_out" / "buildup_in" /
  "generic"), or ``None`` when no section context was provided.
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
    energy: float = 0.0
    drums: float = 0.0
    bass: float = 0.0
    harmonics: float = 0.0
    vocals: float = 0.0
    overall: float = 0.0
    hard_reject: bool = False
    reject_reason: str | None = None
    best_transition: NeuralMixTransition | None = None
    section_pair_class: str | None = None
