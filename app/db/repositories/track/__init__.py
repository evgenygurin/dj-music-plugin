"""Track repository package.

Exports :class:`TrackRepository` — a single class combining core CRUD,
external IDs, library items, stats, and filtering via multiple inheritance.

Callers use the same import as before::

    from app.db.repositories.track import TrackRepository
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.track.core import TrackCoreRepository
from app.db.repositories.track.external_ids import ExternalIdMixin
from app.db.repositories.track.filtering import FilteringMixin
from app.db.repositories.track.library import LibraryMixin
from app.db.repositories.track.stats import StatsMixin


class TrackRepository(
    TrackCoreRepository,
    ExternalIdMixin,
    LibraryMixin,
    StatsMixin,
    FilteringMixin,
):
    """Full track repository combining all sub-repositories.

    Inherits :class:`BaseRepository` (via :class:`TrackCoreRepository`) for
    CRUD and pagination, plus mixin classes for external IDs, library items,
    statistics, and parametric filtering.

    All callers continue to use::

        from app.db.repositories.track import TrackRepository
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)


__all__ = ["TrackRepository"]
