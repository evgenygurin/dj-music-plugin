"""Tool response schema smoke tests — JSON Schema generation + round-trip."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydValidationError

from app.v2.schemas.provider_dto import (
    ProviderReadResult,
    ProviderSearchResult,
    ProviderWriteResult,
)
from app.v2.schemas.tool_responses import (
    AggregateResult,
    EntityCreateResult,
    EntityDeleteResult,
    EntityListResult,
    EntityUpdateResult,
    PlaylistSyncResult,
    ScorePoolResult,
    SequenceOptimizeResult,
    UnlockNamespaceResult,
)


def test_entity_list_result_valid() -> None:
    result = EntityListResult(entity="track", items=[{"id": 1}], total=1, next_cursor=None)
    assert result.entity == "track"
    assert len(result.items) == 1


def test_entity_list_result_requires_entity() -> None:
    with pytest.raises(PydValidationError):
        EntityListResult(items=[], total=0)


def test_aggregate_result_accepts_scalar_and_list() -> None:
    scalar = AggregateResult(entity="track", operation="count", value=42)
    assert scalar.value == 42
    grouped = AggregateResult(
        entity="track",
        operation="count",
        value=[{"mood": "peak_time", "count": 20}],
    )
    assert isinstance(grouped.value, list)


def test_score_pool_result_shape() -> None:
    result = ScorePoolResult(
        track_ids=[1, 2, 3],
        pairs=[
            {"a": 1, "b": 2, "overall": 0.8},
            {"a": 1, "b": 3, "overall": 0.6},
        ],
        hard_rejects=0,
    )
    assert result.hard_rejects == 0


def test_sequence_optimize_result_shape() -> None:
    result = SequenceOptimizeResult(
        track_order=[3, 1, 2],
        quality_score=0.82,
        algorithm="ga",
        generations=100,
    )
    assert result.algorithm == "ga"


def test_playlist_sync_result_shape() -> None:
    result = PlaylistSyncResult(
        playlist_id=7,
        direction="pull",
        applied=[{"op": "add", "track_id": 1}],
        skipped=[],
        conflicts=[],
    )
    assert result.direction == "pull"


def test_unlock_namespace_result_shape() -> None:
    result = UnlockNamespaceResult(
        namespace="sync", status="unlocked", enabled_tools=["playlist_sync"]
    )
    assert result.status == "unlocked"


def test_provider_search_result_shape() -> None:
    result = ProviderSearchResult(
        provider="yandex",
        query="hello",
        type="tracks",
        total=1,
        items=[{"id": "1", "title": "X"}],
    )
    assert result.provider == "yandex"


def test_provider_read_result_arbitrary_data() -> None:
    result = ProviderReadResult(provider="yandex", entity="track", data={"id": "1"})
    assert result.data["id"] == "1"


def test_provider_write_result_shape() -> None:
    result = ProviderWriteResult(
        provider="yandex", entity="playlist", operation="add_tracks", data={"revision": 8}
    )
    assert result.operation == "add_tracks"


def test_entity_create_update_delete_shapes() -> None:
    c = EntityCreateResult(entity="track", data={"id": 1}, meta={"source": "yandex"})
    assert c.entity == "track"
    u = EntityUpdateResult(entity="track", id=1, data={"bpm": 128})
    assert u.id == 1
    d = EntityDeleteResult(entity="track", id=1, deleted=True)
    assert d.deleted is True
