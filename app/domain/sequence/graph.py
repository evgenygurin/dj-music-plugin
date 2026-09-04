"""Bounded candidate graph built from cached transition plans."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.mixing.plan import TransitionPlan


@dataclass(frozen=True, slots=True)
class TransitionEdge:
    source: str
    target: str
    plan: TransitionPlan
    score: float


@dataclass(frozen=True, slots=True)
class CandidateGraph:
    edges: tuple[TransitionEdge, ...]
    top_k: int = 32

    def __post_init__(self) -> None:
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")

    def outgoing(self, source: str) -> tuple[TransitionEdge, ...]:
        ordered = sorted(
            (edge for edge in self.edges if edge.source == source),
            key=lambda edge: (-edge.score, edge.target),
        )
        return tuple(ordered[: self.top_k])

    def has_edge(self, source: str, target: str) -> bool:
        return any(edge.source == source and edge.target == target for edge in self.edges)
