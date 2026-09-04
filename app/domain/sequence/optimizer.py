"""Memory-bounded deterministic Beam Search over cached transition edges."""

from __future__ import annotations

from dataclasses import dataclass

from .constraints import SetConstraints
from .graph import CandidateGraph
from .objective import SequenceObjective
from .state import SetState


@dataclass(frozen=True, slots=True)
class SetPlan:
    tracks: tuple[str, ...]
    transitions: tuple[str, ...]
    score: float
    diagnostics: tuple[str, ...] = ()


class BeamSearchOptimizer:
    def __init__(self, beam_width: int = 8, lookahead: int = 32) -> None:
        if beam_width <= 0 or lookahead <= 0:
            raise ValueError("beam_width and lookahead must be positive")
        self.beam_width = beam_width
        self.lookahead = lookahead

    def optimize(
        self,
        graph: CandidateGraph,
        initial: SetState,
        target: str,
        *,
        constraints: SetConstraints | None = None,
        objective: SequenceObjective | None = None,
    ) -> SetPlan:
        constraints = constraints or SetConstraints()
        objective = objective or SequenceObjective()
        if target in constraints.excluded_tracks:
            raise ValueError(f"target is excluded: {target}")
        beam: list[tuple[SetState, tuple[str, ...], float]] = [(initial, (), 0.0)]
        for _ in range(self.lookahead):
            completed = [
                item for item in beam
                if item[0].current_track == target
                and constraints.mandatory_satisfied(item[0].tracks)
            ]
            if completed:
                best = max(completed, key=lambda item: (item[2], tuple(item[0].tracks)))
                return SetPlan(best[0].tracks, best[1], best[2])
            expanded: list[tuple[SetState, tuple[str, ...], float]] = []
            for state, transitions, total in beam:
                for edge in graph.outgoing(state.current_track):
                    if not constraints.accepts(edge.target, state.tracks):
                        continue
                    next_state = state.append(edge.target)
                    value = objective.edge_value(edge.score)
                    expanded.append(
                        (next_state, (*transitions, edge.plan.execution_identity), total + value)
                    )
            if not expanded:
                break
            expanded.sort(key=lambda item: (-item[2], item[0].tracks))
            beam = expanded[: self.beam_width]
        raise ValueError(f"no path from {initial.current_track} to {target}")
