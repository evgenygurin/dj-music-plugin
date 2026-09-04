"""Bounded-process transition-plan cache port and in-memory implementation."""

from __future__ import annotations

from app.domain.mixing.plan import TransitionPlan


class InMemoryTransitionCache:
    def __init__(self, max_entries: int = 1024) -> None:
        self._max_entries = max_entries
        self._values: dict[str, TransitionPlan] = {}

    def put(self, plan: TransitionPlan) -> None:
        if len(self._values) >= self._max_entries and plan.execution_identity not in self._values:
            self._values.pop(next(iter(self._values)))
        self._values[plan.execution_identity] = plan

    def get(self, identity: str) -> TransitionPlan | None:
        return self._values.get(identity)
