"""Base engine protocol — common lifecycle for runtime singletons."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseEngine(ABC):
    """Common lifecycle hooks for long-lived runtime engines.

    Engines are constructed in a lifespan, started before yield,
    and stopped in the lifespan's finally block. They must be
    safe to call from multiple async tool handlers concurrently.
    """

    @abstractmethod
    async def start(self) -> None:
        """Initialise resources (open streams, prime buffers)."""

    @abstractmethod
    async def stop(self) -> None:
        """Release resources gracefully. Idempotent."""

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable view of current state.

        Used by `watch_decks` long-running tool to push state
        updates via `ctx.report_progress`. Must be cheap (<1 ms).
        """
