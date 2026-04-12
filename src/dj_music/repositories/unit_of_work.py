"""Unit of Work — aggregates all repositories on a single AsyncSession.

Lets services request one object instead of 12 separate ``Depends()``
factories. The session boundary is still owned by the DI provider
(``get_db_session`` in ``app/controllers/dependencies/db.py``), so
commit/rollback behaviour is unchanged.

Usage::

    async def get_uow(session = Depends(get_db_session)) -> UnitOfWork:
        return UnitOfWork(session)

    @mcp.tool
    async def list_tracks(limit: int = 50, uow = Depends(get_uow)):
        return await uow.tracks.list_all(limit=limit)
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.repositories.audio import AudioRepository
from dj_music.repositories.candidate import CandidateRepository
from dj_music.repositories.embedding import EmbeddingRepository
from dj_music.repositories.export import ExportRepository
from dj_music.repositories.feature import FeatureRepository
from dj_music.repositories.ingestion import IngestionRepository
from dj_music.repositories.metadata import MetadataRepository
from dj_music.repositories.playlist import PlaylistRepository
from dj_music.repositories.set import SetRepository
from dj_music.repositories.track import TrackRepository
from dj_music.repositories.transition import TransitionRepository


class UnitOfWork:
    """Aggregates every repository on one shared AsyncSession.

    The session lifecycle (commit / rollback / close) is managed by
    the dependency-injection provider that constructs the UoW —
    typically ``get_db_session`` in ``app/controllers/dependencies/db.py``.
    """

    __slots__ = (
        "audio",
        "candidates",
        "embeddings",
        "exports",
        "features",
        "ingestion",
        "metadata",
        "playlists",
        "session",
        "sets",
        "tracks",
        "transitions",
    )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tracks = TrackRepository(session)
        self.playlists = PlaylistRepository(session)
        self.sets = SetRepository(session)
        self.features = FeatureRepository(session)
        self.transitions = TransitionRepository(session)
        self.audio = AudioRepository(session)
        self.candidates = CandidateRepository(session)
        self.embeddings = EmbeddingRepository(session)
        self.exports = ExportRepository(session)
        self.ingestion = IngestionRepository(session)
        self.metadata = MetadataRepository(session)


__all__ = ["UnitOfWork"]
