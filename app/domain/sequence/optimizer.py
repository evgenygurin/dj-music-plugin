"""Memory-bounded deterministic Beam Search over cached transition edges."""

from __future__ import annotations

from dataclasses import dataclass

from .graph import CandidateGraph
from .state import SetState


@dataclass(frozen=True, slots=True)
class SetPlan:
    tracks: tuple[str, ...]
    transitions: tuple[str, ...]
    score: float


class BeamSearchOptimizer:
    def __init__(self, beam_width: int = 8, lookahead: int = 32) -> None:
        if beam_width <= 0 or lookahead <= 0:
            raise ValueError("beam_width and lookahead must be positive")
        self.beam_width = beam_width
        self.lookahead = lookahead

    def optimize(self, graph: CandidateGraph, initial: SetState, target: str) -> SetPlan:
        beam: list[tuple[tuple[str, ...], tuple[str, ...], float]] = [(initial.tracks, (), 0.0)]
        for _ in range(self.lookahead):
            completed = [item for item in beam if item[0][-1] == target]
            if completed:
                best = max(completed, key=lambda item: (item[2], tuple(item[0])))
                return SetPlan(*best)
            expanded: list[tuple[tuple[str, ...], tuple[str, ...], float]] = []
            for tracks, transitions, score in beam:
                for edge in graph.outgoing(tracks[-1]):
                    if edge.target in tracks:
                        continue
                    expanded.append(
                        (
                            (*tracks, edge.target),
                            (*transitions, edge.plan.execution_identity),
                            score + edge.score,
                        )
                    )
            if not expanded:
                break
            expanded.sort(key=lambda item: (-item[2], item[0]))
            beam = expanded[: self.beam_width]
        raise ValueError(f"no path from {initial.current_track} to {target}")
