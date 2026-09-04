"""Bounded transition-plan cache port and in-memory implementation."""

from __future__ import annotations

from collections import OrderedDict

from app.domain.mixing.plan import TransitionPlan


class InMemoryTransitionCache:
    def __init__(self, max_entries: int = 1024) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._max_entries = max_entries
        self._values: OrderedDict[str, TransitionPlan] = OrderedDict()

    def put(self, plan: TransitionPlan) -> None:
        key = plan.execution_identity
        self._values.pop(key, None)
        self._values[key] = plan
        while len(self._values) > self._max_entries:
            self._values.popitem(last=False)

    def get(self, identity: str) -> TransitionPlan | None:
        plan = self._values.get(identity)
        if plan is not None:
            self._values.move_to_end(identity)
        return plan

    def __len__(self) -> int:
        return len(self._values)
