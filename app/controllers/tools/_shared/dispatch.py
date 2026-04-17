"""Action dispatcher for ``action``-parameterised MCP tools.

Tools like ``platform_playlists``, ``platform_liked_tracks`` and ``manage_*`` accept an
``action`` string (``"create"``, ``"delete"``, ``"add_tracks"`` ...) and
switch behaviour based on it. The legacy implementation used long
``if/elif`` chains that violated the Open-Closed Principle — every new
action required editing the same function.

:class:`ActionDispatcher` is a minimal **Command + Registry** pattern:
handlers register themselves via :meth:`register`, and :meth:`dispatch`
invokes the matching one. Adding a new action becomes a pure addition.

Example::

    dispatcher: ActionDispatcher[PlaylistResult] = ActionDispatcher()

    @dispatcher.register("create")
    async def _create(data: dict, ym: YMClient) -> PlaylistResult:
        ...

    @dispatcher.register("rename")
    async def _rename(data: dict, ym: YMClient) -> PlaylistResult:
        ...

    # Inside the @tool:
    return await dispatcher.dispatch(action, data, ym)

The dispatcher is generic over the result type but not over the handler
signature — handlers all take identical positional arguments supplied
by the caller. This keeps the dispatch site type-safe without dragging
in variadic generics.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

ResultT = TypeVar("ResultT")
HandlerT = Callable[..., Awaitable["ResultT"]]


class UnknownActionError(ValueError):
    """Raised when :meth:`ActionDispatcher.dispatch` gets an unregistered action."""


class ActionDispatcher(Generic[ResultT]):
    """Registry-based action → handler lookup.

    Thread-safety
    -------------
    Registration happens at module import time; runtime dispatch is
    read-only and therefore thread-safe. Do not mutate the registry
    after the module is imported.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, HandlerT[ResultT]] = {}

    def register(self, action: str) -> Callable[[HandlerT[ResultT]], HandlerT[ResultT]]:
        """Decorator-factory that registers ``handler`` under ``action``.

        Re-registering the same action raises :class:`ValueError` — the
        loud failure mode is intentional to catch copy-paste bugs like
        BUG-017.
        """

        def decorator(handler: HandlerT[ResultT]) -> HandlerT[ResultT]:
            if action in self._handlers:
                raise ValueError(f"duplicate action handler: {action!r}")
            self._handlers[action] = handler
            return handler

        return decorator

    @property
    def actions(self) -> frozenset[str]:
        """All registered action names (stable, immutable)."""
        return frozenset(self._handlers)

    async def dispatch(self, action: str, /, *args: object, **kwargs: object) -> ResultT:
        """Invoke the handler registered for ``action``.

        Raises
        ------
        UnknownActionError
            If ``action`` is not registered.
        """
        handler = self._handlers.get(action)
        if handler is None:
            known = ", ".join(sorted(self._handlers)) or "<none>"
            raise UnknownActionError(f"unknown action {action!r}; known: {known}")
        return await handler(*args, **kwargs)
