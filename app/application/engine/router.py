"""Feature-flagged routing between legacy and universal engines."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.application.engine.mode import EngineMode, EngineSelection

T = TypeVar("T")
C = TypeVar("C")


@dataclass(frozen=True, slots=True)
class EngineRunResult(Generic[T, C]):
    """The selected engine result plus optional shadow diagnostics."""

    value: T
    comparison: C | None = None


class TransitionEngineRouter(Generic[T, C]):
    """Route one transition request according to the rollout mode.

    In shadow mode the legacy engine is evaluated first, then the new engine
    is evaluated for the same request and returned as the authoritative value.
    The comparison callback receives both results and is intentionally opaque
    to this application boundary.
    """

    def __init__(
        self,
        selection: EngineSelection,
        *,
        legacy: Callable[[], T],
        new: Callable[[], T] | None = None,
        compare: Callable[[T, T], C] | None = None,
    ) -> None:
        self._selection = selection
        self._legacy = legacy
        self._new = new
        self._compare = compare

    def run(self) -> EngineRunResult[T, C]:
        if self._selection.engine is EngineMode.LEGACY:
            return EngineRunResult(self._legacy())

        if self._new is None:
            raise RuntimeError("new engine is required for non-legacy transition mode")

        if self._selection.engine is EngineMode.NEW:
            return EngineRunResult(self._new())

        legacy_result = self._legacy()
        new_result = self._new()
        comparison = self._compare(legacy_result, new_result) if self._compare else None
        return EngineRunResult(new_result, comparison)
