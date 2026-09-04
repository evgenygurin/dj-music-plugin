"""Deterministic policies over already validated musical candidates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .scores import MusicalScore


class SelectionPolicy(StrEnum):
    BEST = "best"
    SAFEST = "safest"
    MOST_HARMONIC = "most_harmonic"
    MOST_ENERGETIC = "most_energetic"
    MOST_GROOVY = "most_groovy"
    MOST_CREATIVE = "most_creative"
    MOST_SMOOTH = "most_smooth"
    EXPLICIT_PROFILE = "explicit_profile"


@dataclass(frozen=True, slots=True)
class SelectionResult:
    selected: str
    alternatives: tuple[str, ...] = ()


def select(
    scores: tuple[tuple[str, MusicalScore], ...], policy: SelectionPolicy
) -> SelectionResult:
    acceptable = [(name, score) for name, score in scores if not score.hard_rejected]
    if not acceptable:
        raise ValueError("no acceptable candidates")
    dimension = {
        SelectionPolicy.MOST_HARMONIC: "harmony",
        SelectionPolicy.MOST_ENERGETIC: "energy",
        SelectionPolicy.MOST_GROOVY: "groove",
        SelectionPolicy.MOST_SMOOTH: "timbre",
    }.get(policy)
    if dimension:
        ordered = sorted(
            acceptable,
            key=lambda item: (-item[1].dimension_value(dimension), item[0]),
        )
    else:
        ordered = sorted(
            acceptable, key=lambda item: (-item[1].total(), item[0])
        )
    return SelectionResult(ordered[0][0], tuple(name for name, _ in ordered[1:]))
