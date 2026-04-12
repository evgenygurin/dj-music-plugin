"""Repository port interfaces (Protocol). Services depend on these."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dj_music.core.utils.pagination import CursorPage


@runtime_checkable
class TrackRepositoryPort(Protocol):
    async def get_by_id(self, id: int) -> object | None: ...
    async def list_all(self, limit: int = 20, cursor: str | None = None) -> CursorPage[object]: ...
    async def create(self, instance: object) -> object: ...
