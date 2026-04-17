"""TransitionScore dataclass — the result type of TransitionScorer.

Held in its own module so ``recommend_style`` and other consumers can
import it without dragging the full scorer engine. The shape is part of
the public API; persisted DB rows from ``transitions`` are reconstructed
into TransitionScore instances by ``app/services/set/scoring.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


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
