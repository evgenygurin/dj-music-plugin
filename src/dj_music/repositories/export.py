"""Export repository — thin wrapper around BaseRepository."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.export import AppExport
from dj_music.repositories.base import BaseRepository


class ExportRepository(BaseRepository[AppExport]):
    """Repository for :class:`AppExport`. No extra methods needed."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AppExport)
