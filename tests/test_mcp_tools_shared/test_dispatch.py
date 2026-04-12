"""Unit tests for ActionDispatcher."""

from __future__ import annotations

import pytest

from dj_music.tools._shared.dispatch import ActionDispatcher, UnknownActionError


async def test_register_and_dispatch() -> None:
    d: ActionDispatcher[int] = ActionDispatcher()

    @d.register("double")
    async def _double(x: int) -> int:
        return x * 2

    @d.register("negate")
    async def _negate(x: int) -> int:
        return -x

    assert await d.dispatch("double", 5) == 10
    assert await d.dispatch("negate", 3) == -3


async def test_dispatch_with_kwargs() -> None:
    d: ActionDispatcher[str] = ActionDispatcher()

    @d.register("join")
    async def _join(*, a: str, b: str) -> str:
        return f"{a}-{b}"

    assert await d.dispatch("join", a="x", b="y") == "x-y"


def test_duplicate_registration_rejected() -> None:
    d: ActionDispatcher[int] = ActionDispatcher()

    @d.register("same")
    async def _h1() -> int:
        return 1

    with pytest.raises(ValueError, match="duplicate action handler"):

        @d.register("same")
        async def _h2() -> int:
            return 2


async def test_unknown_action_raises() -> None:
    d: ActionDispatcher[int] = ActionDispatcher()

    @d.register("known")
    async def _known() -> int:
        return 0

    try:
        await d.dispatch("missing")
    except UnknownActionError as exc:
        assert str(exc) == "unknown action 'missing'; known: known"
    else:
        pytest.fail("Expected UnknownActionError")


def test_actions_property_returns_frozen_set() -> None:
    d: ActionDispatcher[None] = ActionDispatcher()

    @d.register("a")
    async def _a() -> None: ...

    @d.register("b")
    async def _b() -> None: ...

    assert d.actions == frozenset({"a", "b"})
    assert isinstance(d.actions, frozenset)
