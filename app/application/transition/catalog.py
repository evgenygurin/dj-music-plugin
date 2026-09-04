"""Infrastructure adapter for transition candidate catalog access."""

from __future__ import annotations

from typing import Any

from app.repositories.unit_of_work import UnitOfWork


class UowCandidateCatalog:
    """Adapt the repository unit of work to the candidate use-case port."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def features(self, track_ids: list[int]) -> dict[int, Any]:
        return await self._uow.track_features.get_scoring_features_batch(track_ids)

    async def track_ids(self) -> list[int]:
        page = await self._uow.tracks.filter(
            where={"has_features": True},
            order=["id"],
            limit=10000,
        )
        return [row.id for row in page.items]

    async def titles(self, track_ids: list[int]) -> dict[int, str]:
        tracks = await self._uow.tracks.get_many(track_ids) if track_ids else {}
        return {track_id: getattr(track, "title", "") or "" for track_id, track in tracks.items()}
