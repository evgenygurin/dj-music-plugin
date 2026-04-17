"""Unit of Work — transaction boundary = tool call.

Per blueprint §10. Phase 1 ships the skeleton with no registered repositories.
Phase 2 adds lazy ``@property`` accessors for each entity's repository as
models land.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork:
    """One UoW per tool call. Commit on success, rollback on exception.

    Usage in tools (Phase 3+):
        async def my_tool(uow: UnitOfWork = Depends(get_uow)) -> ...:
            async with uow:
                track = await uow.tracks.get(42)
                ...

    In Phase 1 there are no ``uow.<entity>`` properties yet — Phase 2 adds
    them as each repository lands.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is None:
            await self.session.commit()
        else:
            await self.session.rollback()
