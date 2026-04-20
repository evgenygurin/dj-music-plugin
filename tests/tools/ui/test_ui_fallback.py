"""Fallback-path tests — ``supports_ui`` returns False → Pydantic models.

We exercise each UI tool's ``_gather``/``_compute`` helper via a direct call
with a mocked UoW so we do not need a Prefab-capable client. Each call must
produce a Pydantic fallback payload that matches the UI tool's fallback
schema.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tools.ui._fallback import (
    CamelotWheelFallback,
    DashboardFallback,
    LibraryAuditFallback,
    ScorePoolMatrixFallback,
    SetViewFallback,
    TransitionScoreFallback,
    fallback_or,
    supports_ui,
)


def test_supports_ui_false_when_no_ctx_method() -> None:
    ctx = MagicMock(spec=[])  # no client_supports_extension
    assert supports_ui(ctx) is False


def test_supports_ui_false_when_check_returns_false() -> None:
    ctx = MagicMock()
    ctx.client_supports_extension = MagicMock(return_value=False)
    assert supports_ui(ctx) is False


def test_supports_ui_true_when_check_returns_true() -> None:
    ctx = MagicMock()
    ctx.client_supports_extension = MagicMock(return_value=True)
    assert supports_ui(ctx) is True


def test_supports_ui_swallows_exceptions() -> None:
    ctx = MagicMock()
    ctx.client_supports_extension = MagicMock(side_effect=RuntimeError("boom"))
    assert supports_ui(ctx) is False


def test_fallback_or_validates_models() -> None:
    # Each fallback model accepts the minimal payload shape.
    fallback_or(
        SetViewFallback,
        {
            "set_id": 1,
            "name": None,
            "template_name": None,
            "version_id": None,
            "quality_score": None,
            "tracks": [],
            "energy_arc": [],
            "transitions": [],
        },
    )
    fallback_or(
        TransitionScoreFallback,
        {
            "from_track_id": 1,
            "to_track_id": 2,
            "components": {"bpm": 0.5},
            "overall": 0.5,
            "hard_reject": False,
            "reject_reason": None,
            "style": "BASS_SWAP_LONG",
            "style_bars": 32,
            "style_reason": None,
        },
    )
    fallback_or(
        LibraryAuditFallback,
        {
            "playlist_id": None,
            "total_tracks": 0,
            "passed": 0,
            "failed": 0,
            "coverage": 0.0,
            "per_track": [],
            "subgenre_distribution": {},
        },
    )
    fallback_or(
        ScorePoolMatrixFallback,
        {"track_ids": [], "cells": [], "hard_rejects": 0},
    )
    fallback_or(
        DashboardFallback,
        {
            "total_tracks": 0,
            "analyzed_tracks": 0,
            "coverage": 0.0,
            "bpm_histogram": {},
            "mood_distribution": {},
            "camelot_distribution": {},
        },
    )
    fallback_or(
        CamelotWheelFallback,
        {"playlist_id": None, "total_tracks": 0, "slots": []},
    )


@pytest.mark.asyncio
async def test_ui_set_view_returns_fallback_when_no_ui_support() -> None:
    from app.tools.ui.set_view import _gather

    # Minimal UoW mock: set exists, no version. Build a real object for the
    # set row so Pydantic string validation does not choke on MagicMock.
    class _Set:
        id = 1
        name = "Test Set"
        template_name = "classic_60"

    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=_Set())
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(return_value=None)
    uow.set_versions.get_items = AsyncMock(return_value=[])
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(return_value=None)
    uow.tracks.get_many = AsyncMock(return_value={})
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    uow.transitions = MagicMock()
    uow.transitions.get_by_pair = AsyncMock(return_value=None)
    uow.transitions.get_pairs_batch = AsyncMock(return_value={})

    data = await _gather(uow, set_id=1, version_id=None)
    result = fallback_or(SetViewFallback, data)
    assert result.set_id == 1
    assert result.name == "Test Set"
    assert result.tracks == []
