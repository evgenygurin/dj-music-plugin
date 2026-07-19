from __future__ import annotations

from app.models.track_features import TrackSection
from app.repositories.base import BaseRepository


class TrackSectionRepository(BaseRepository[TrackSection]):
    model = TrackSection
