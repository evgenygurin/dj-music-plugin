"""Audit iter 5: three live-MCP probes turned up silent failures —
inputs that should be rejected up front but instead produced empty
results, raw Python tracebacks, or silently-violated contradictions.

* T-2: ``sequence_optimize(pinned=[146,147], excluded=[146])`` -
  track 146 in BOTH pinned and excluded was silently allowed; the
  optimizer kept it (pinned won). The contradiction should fail
  fast with a clear error.

* T-3: ``entity_list(track, fields='unknown_preset')`` returned
  ``[{},{},{},{},{}]`` - 5 empty rows. ``resolve_field_projection``
  fell through the CSV path and produced ``{'unknown_preset'}``,
  which ``model_dump(include=...)`` silently accepted, dumping an
  empty object per row. Silent data loss.

* T-4: ``provider_search(query='')`` leaked the raw Python error
  ``'str' object has no attribute 'get'`` from the YM client
  parsing an empty response. Empty query is invalid input - reject
  before hitting the network.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.errors import ValidationError


@pytest.mark.asyncio
async def test_sequence_optimize_rejects_pinned_excluded_overlap() -> None:
    """T-2: pinned ∩ excluded must not overlap."""
    from app.tools.compute.sequence_optimize import sequence_optimize

    uow = MagicMock()
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})

    with pytest.raises(ValidationError, match=r"(?i)pinned.*excluded"):
        await sequence_optimize(
            track_ids=[146, 147, 148],
            algorithm="greedy",
            pinned=[146, 147],
            excluded=[146],
            uow=uow,
            scorer=MagicMock(),
            optimizer_builder=MagicMock(),
        )


def test_resolve_field_projection_rejects_unknown_preset_name() -> None:
    """T-3: a single-token string that isn't a preset and isn't a
    declared field on the view should fail loudly, not produce an
    empty projection that strips every row to {}.
    """
    from app.registry.entity import EntityConfig, resolve_field_projection

    cfg = MagicMock(spec=EntityConfig)
    cfg.field_presets = {"id": ["id"], "summary": ["id", "title"], "full": "*"}
    cfg.default_preset = "full"
    # MagicMock view_schema with declared fields {id, title, duration_ms}.
    cfg.view_schema = MagicMock()
    cfg.view_schema.model_fields = {"id": None, "title": None, "duration_ms": None}

    with pytest.raises(ValidationError, match=r"(?i)unknown_preset"):
        resolve_field_projection("unknown_preset", cfg)


def test_resolve_field_projection_rejects_unknown_field_in_list() -> None:
    """T-3 (cont.): explicit ``fields=['id', 'bogus']`` must complain about
    ``bogus`` instead of silently dropping it from each row."""
    from app.registry.entity import EntityConfig, resolve_field_projection

    cfg = MagicMock(spec=EntityConfig)
    cfg.field_presets = {"id": ["id"], "full": "*"}
    cfg.default_preset = "full"
    cfg.view_schema = MagicMock()
    cfg.view_schema.model_fields = {"id": None, "title": None}

    with pytest.raises(ValidationError, match=r"(?i)bogus"):
        resolve_field_projection(["id", "bogus"], cfg)


def test_resolve_field_projection_accepts_known_fields() -> None:
    """Sanity: real fields still pass."""
    from app.registry.entity import EntityConfig, resolve_field_projection

    cfg = MagicMock(spec=EntityConfig)
    cfg.field_presets = {"id": ["id"], "full": "*"}
    cfg.default_preset = "full"
    cfg.view_schema = MagicMock()
    cfg.view_schema.model_fields = {"id": None, "title": None}

    assert resolve_field_projection(["id", "title"], cfg) == {"id", "title"}


@pytest.mark.asyncio
async def test_provider_search_rejects_empty_query() -> None:
    """T-4: empty query is invalid input. Must raise ValidationError
    before issuing the network call (or letting the YM client crash
    on an empty response shape).
    """
    from app.tools.provider.search import provider_search

    registry = MagicMock()
    with pytest.raises(ValidationError, match=r"(?i)empty"):
        await provider_search(
            provider="yandex",
            query="",
            type="tracks",
            limit=5,
            registry=registry,
        )


@pytest.mark.asyncio
async def test_provider_search_rejects_whitespace_only_query() -> None:
    from app.tools.provider.search import provider_search

    registry = MagicMock()
    with pytest.raises(ValidationError, match=r"(?i)empty"):
        await provider_search(
            provider="yandex",
            query="   ",
            type="tracks",
            limit=5,
            registry=registry,
        )
