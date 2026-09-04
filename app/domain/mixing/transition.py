"""Auditable transition decisions."""

from __future__ import annotations

from dataclasses import dataclass

from .plan import TransitionPlan
from .selection import SelectionPolicy


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    selected: TransitionPlan
    alternatives: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    policy: SelectionPolicy
    diagnostics: tuple[str, ...] = ()
    score: float = 0.0
    technical_margin: float = 0.0
    dimension_scores: tuple[tuple[str, float], ...] = ()
