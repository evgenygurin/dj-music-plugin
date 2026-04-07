"""Unit tests for the ToolContext facade."""

from __future__ import annotations

from typing import Any

from app.mcp.tools._shared.context import ToolContext


class _FakeCtx:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warns: list[str] = []
        self.progress: list[tuple[int, int]] = []
        self.elicited: list[str] = []
        self.elicit_return: Any = "ok"

    async def info(self, msg: str) -> None:
        self.infos.append(msg)

    async def warning(self, msg: str) -> None:
        self.warns.append(msg)

    async def report_progress(self, current: int, total: int) -> None:
        self.progress.append((current, total))

    async def elicit(self, msg: str, response_type: Any = None) -> Any:
        self.elicited.append(msg)
        return self.elicit_return


async def test_inactive_context_is_silent() -> None:
    log = ToolContext(None)
    assert log.active is False
    assert log.raw is None
    # None of these should raise.
    await log.info("hello")
    await log.warn("uh oh")
    await log.progress(1, 10)
    assert await log.elicit("continue?", default="abort") == "abort"


async def test_active_context_forwards() -> None:
    fake = _FakeCtx()
    log = ToolContext(fake)  # type: ignore[arg-type]
    assert log.active is True
    assert log.raw is fake

    await log.info("started")
    await log.warn("late")
    await log.progress(3, 5)
    assert await log.elicit("ok?") == "ok"

    assert fake.infos == ["started"]
    assert fake.warns == ["late"]
    assert fake.progress == [(3, 5)]
    assert fake.elicited == ["ok?"]


async def test_warn_falls_back_to_info_when_warning_absent() -> None:
    class _MinimalCtx:
        def __init__(self) -> None:
            self.infos: list[str] = []

        async def info(self, msg: str) -> None:
            self.infos.append(msg)

    fake = _MinimalCtx()
    log = ToolContext(fake)  # type: ignore[arg-type]
    await log.warn("fallback")
    assert fake.infos == ["WARNING: fallback"]
