"""Application facade for set-level planning."""

from __future__ import annotations

from app.domain.sequence.graph import CandidateGraph
from app.domain.sequence.optimizer import BeamSearchOptimizer, SetPlan
from app.domain.sequence.state import SetState


class SequencePlanner:
    def __init__(self, beam_width: int = 8, lookahead: int = 32) -> None:
        self._optimizer = BeamSearchOptimizer(beam_width, lookahead)

    def plan(self, graph: CandidateGraph, start: str, target: str) -> SetPlan:
        return self._optimizer.optimize(graph, SetState((start,)), target)
