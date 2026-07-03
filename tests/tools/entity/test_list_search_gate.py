"""``entity_list.search`` must not be a silent no-op on non-searchable entities.

Live probe 2026-07-03: ``entity_list(entity="track_affinity",
search="x")`` returned the full unfiltered list — the entity declares no
``searchable_fields``, so the ``if search and config.searchable_fields``
guard skipped the search term entirely. Same false-contract class as the
old ``include_relations`` no-op: the caller believes they filtered but
got everything. Reject up front with a typed error naming the searchable
entities.

Entities WITH searchable_fields (track, playlist, set, set_version,
audio_file, scoring_profile) keep working; the 5 without
(track_features, transition, transition_history, track_feedback,
track_affinity) now raise instead of lying.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastmcp.client import Client

NON_SEARCHABLE = [
    "track_features",
    "transition",
    "transition_history",
    "track_feedback",
    "track_affinity",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("entity", NON_SEARCHABLE)
async def test_search_on_non_searchable_entity_rejected(mcp_client: Client, entity: str) -> None:
    with pytest.raises(Exception, match="does not support free-text search"):
        await mcp_client.call_tool("entity_list", {"entity": entity, "search": "anything"})


@pytest.mark.asyncio
async def test_search_on_searchable_entity_still_works(
    mcp_client: Client, mock_uow: MagicMock
) -> None:
    page = MagicMock(items=[], next_cursor=None, total=None)
    mock_uow.tracks.filter.return_value = page
    # Must not raise — track declares searchable_fields=("title", "sort_title").
    result = await mcp_client.call_tool("entity_list", {"entity": "track", "search": "acid"})
    data = result.structured_content or result.data
    assert data["entity"] == "track"
