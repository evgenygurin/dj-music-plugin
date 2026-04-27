"""End-to-end regression: ``has_features`` must survive the
``normalize_bare_fields`` pre-processor in ``entity_list``.

Live MCP probe after v1.2.0 caught that the schema-level fix was
correct but invisible behind the dispatcher: ``normalize_bare_fields``
adds ``__eq`` to every bare key, turning ``{"has_features": true}``
into ``{"has_features__eq": true}`` before the Pydantic filter runs —
and ``TrackFilter`` declared ``has_features`` without that suffix.
Result: real users still saw ``extra_forbidden: has_features__eq``.

The unit tests pass because they hit the repository directly with
the already-normalized key. This module hits the v1 dispatcher to
guard the full path. Same class as v1.0.13 ("declared but not
applied") — fix at the layer the user actually touches.
"""

from __future__ import annotations

import pytest

from app.shared.filters import normalize_bare_fields


def test_normalize_bare_fields_keeps_has_features_compatible_with_schema() -> None:
    """``normalize_bare_fields`` adds ``__eq`` to every bare key by
    design (see entity_list dispatcher). ``TrackFilter`` must therefore
    accept the normalized form, otherwise the dispatcher rejects the
    request before the repository can pop it."""
    from app.schemas.track import TrackFilter

    normalized = normalize_bare_fields({"has_features": True})
    assert "has_features__eq" in normalized
    # The whole point of this regression: the schema must accept the
    # post-normalize shape that the dispatcher actually emits.
    TrackFilter.model_validate(normalized)


def test_track_filter_accepts_has_features_eq_directly() -> None:
    from app.schemas.track import TrackFilter

    TrackFilter.model_validate({"has_features__eq": True})
    TrackFilter.model_validate({"has_features__eq": False})
    TrackFilter.model_validate({"has_features__eq": None})


@pytest.mark.asyncio
async def test_entity_list_dispatcher_accepts_has_features_filter(
    mcp_client: object, mock_uow: object
) -> None:
    """End-to-end: dispatcher → normalize_bare_fields → schema.validate
    → repo.filter must not reject ``has_features=True``.
    """
    from unittest.mock import MagicMock

    page = MagicMock(items=[], next_cursor=None, total=0)
    mock_uow.tracks.filter.return_value = page  # type: ignore[attr-defined]

    result = await mcp_client.call_tool(  # type: ignore[attr-defined]
        "entity_list",
        {"entity": "track", "filters": {"has_features": True}, "limit": 5},
    )
    data = result.structured_content or result.data
    assert data["entity"] == "track"
