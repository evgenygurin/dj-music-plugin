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

    def outgoing(self, source: str) -> tuple[TransitionEdge, ...]:
        return tuple(
            sorted(
                (edge for edge in self.edges if edge.source == source),
                key=lambda edge: (-edge.score, edge.target),
            )
        )

    def has_edge(self, source: str, target: str) -> bool:
        return any(edge.source == source and edge.target == target for edge in self.edges)
