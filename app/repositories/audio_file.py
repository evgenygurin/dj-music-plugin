"""Audio file repository."""

from __future__ import annotations

from sqlalchemy import select

from app.models.audio_file import DjBeatgrid, DjLibraryItem
from app.repositories.base import BaseRepository


class AudioFileRepository(BaseRepository[DjLibraryItem]):
    model = DjLibraryItem

    async def get_for_track(self, track_id: int) -> DjLibraryItem | None:
        stmt = select(DjLibraryItem).where(DjLibraryItem.track_id == track_id).limit(1)
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    # Name used by handlers; alias kept for resource/handler compatibility.
    get_by_track_id = get_for_track

    async def register_beatgrid(
        self,
        library_item_id: int,
        *,
        bpm: float,
        first_downbeat_ms: float,
        canonical: bool = True,
    ) -> DjBeatgrid:
        bg = DjBeatgrid(
            library_item_id=library_item_id,
            bpm=bpm,
            first_downbeat_ms=first_downbeat_ms,
            canonical=canonical,
        )
        self.session.add(bg)
        await self.session.flush()
        return bg
