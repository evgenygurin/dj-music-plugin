from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.transition.catalog import UowCandidateCatalog


@pytest.mark.asyncio
async def test_track_ids_uses_track_repository_filter_contract() -> None:
    tracks = MagicMock()
    tracks.filter = AsyncMock(
        return_value=SimpleNamespace(items=[SimpleNamespace(id=3), SimpleNamespace(id=7)])
    )
    uow = SimpleNamespace(tracks=tracks)

    result = await UowCandidateCatalog(uow).track_ids()

    assert result == [3, 7]
    tracks.filter.assert_awaited_once_with(
        where={"has_features": True},
        order=["id"],
        limit=10000,
    )
