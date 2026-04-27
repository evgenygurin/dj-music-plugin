"""Audit O-3: suggest_next / suggest_replacement must surface a ``reason``
when ``candidates`` is empty so consumers can distinguish "no data" from
"data exists, all filtered out" from "repo method not implemented yet".
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.track import track_suggest_next, track_suggest_replacement


@pytest.mark.asyncio
async def test_suggest_next_reason_when_no_history() -> None:
    uow = MagicMock()
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(return_value=MagicMock(id=42, title="X"))
    uow.transitions = MagicMock()
    uow.transitions.list_from = AsyncMock(return_value=[])
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})

    payload = json.loads(await track_suggest_next(id=42, limit=5, uow=uow))
    assert payload["candidates"] == []
    assert payload["reason"] == "no historical transitions logged for this track"


@pytest.mark.asyncio
async def test_suggest_next_reason_when_repo_missing_list_from() -> None:
    uow = MagicMock()
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(return_value=MagicMock(id=42, title="X"))
    uow.transitions = MagicMock(spec=[])  # no ``list_from``
    payload = json.loads(await track_suggest_next(id=42, limit=5, uow=uow))
    assert payload["candidates"] == []
    assert "list_from" in (payload["reason"] or "")


@pytest.mark.asyncio
async def test_suggest_replacement_reason_when_no_versions() -> None:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=MagicMock(id=1))
    uow.set_versions = MagicMock()
    uow.set_versions.latest_version = AsyncMock(return_value=None)

    payload = json.loads(await track_suggest_replacement(id=42, set_id=1, position=0, uow=uow))
    assert payload["candidates"] == []
    assert payload["reason"] == "set has no versions yet"


@pytest.mark.asyncio
async def test_suggest_replacement_reason_when_target_has_no_features() -> None:
    version = MagicMock(id=99)
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=MagicMock(id=1))
    uow.set_versions = MagicMock()
    uow.set_versions.latest_version = AsyncMock(return_value=version)
    uow.set_versions.get_items = AsyncMock(return_value=[])
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})

    payload = json.loads(await track_suggest_replacement(id=777, set_id=1, position=0, uow=uow))
    assert payload["candidates"] == []
    assert "scoring features" in (payload["reason"] or "")
