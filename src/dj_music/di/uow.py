"""Unit of work dependency factories."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.di.db import get_db_session
from dj_music.repositories.unit_of_work import UnitOfWork


def get_uow(session: AsyncSession = Depends(get_db_session)) -> UnitOfWork:  # noqa: B008
    """Build a UnitOfWork bound to the current request session."""
    return UnitOfWork(session)
