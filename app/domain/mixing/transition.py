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
