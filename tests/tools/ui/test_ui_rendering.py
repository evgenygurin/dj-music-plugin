"""Rendering-path tests — ``supports_ui`` True → prefab_ui component tree.

We bypass the FastMCP client (which would require a Prefab-capable
transport) and call the tool function directly with a stubbed Context
whose ``client_supports_extension`` returns True. The assertion is that
the return value is an instance of ``prefab_ui.components.Column`` — i.e.
the tool actually builds a UI tree instead of a Pydantic model.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from prefab_ui.components import Column


def _ui_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.client_supports_extension = MagicMock(return_value=True)
    return ctx


def _uow_stub(set_name: str = "Test Set") -> MagicMock:
    uow = MagicMock()
    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(
        return_value=MagicMock(id=1, name=set_name, template_name="classic_60")
    )
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(
        return_value=MagicMock(id=11, set_id=1, quality_score=0.75)
    )
    uow.set_versions.get_items = AsyncMock(return_value=[])
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(return_value=None)
    uow.tracks.get_many = AsyncMock(return_value={})
    uow.playlists = MagicMock()
    uow.playlists.get = AsyncMock(return_value=None)
    uow.playlists.get_track_ids = AsyncMock(return_value=[])
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={})
    uow.track_features.count = AsyncMock(return_value=0)
    uow.track_features.session = MagicMock()
    uow.tracks.count = AsyncMock(return_value=0)
    uow.tracks.filter = AsyncMock(return_value=MagicMock(items=[]))
    uow.transitions = MagicMock()
    uow.transitions.get_by_pair = AsyncMock(return_value=None)
    uow.transitions.get_pair = AsyncMock(return_value=None)
    uow.transitions.get_pairs_batch = AsyncMock(return_value={})
    return uow


@pytest.mark.asyncio
async def test_ui_set_view_renders_column() -> None:
    from app.tools.ui.set_view import ui_set_view

    uow = _uow_stub()
    ctx = _ui_ctx()
    result = await ui_set_view(set_id=1, version_id=None, uow=uow, ctx=ctx)
    assert isinstance(result, Column)


@pytest.mark.asyncio
async def test_ui_library_audit_renders_column_with_empty_library() -> None:
    from app.tools.ui.library_audit import ui_library_audit

    uow = _uow_stub()
    ctx = _ui_ctx()
    result = await ui_library_audit(playlist_id=None, uow=uow, ctx=ctx)
    assert isinstance(result, Column)


@pytest.mark.asyncio
async def test_ui_library_dashboard_renders_column() -> None:
    from app.tools.ui.library_dashboard import ui_library_dashboard

    uow = _uow_stub()
    # session.execute must return an iterable of rows
    execute_result = MagicMock()
    execute_result.all = MagicMock(return_value=[])
    uow.track_features.session.execute = AsyncMock(return_value=execute_result)
    ctx = _ui_ctx()
    result = await ui_library_dashboard(uow=uow, ctx=ctx)
    assert isinstance(result, Column)


@pytest.mark.asyncio
async def test_ui_camelot_wheel_renders_column_when_empty() -> None:
    from app.tools.ui.camelot_wheel import ui_camelot_wheel

    uow = _uow_stub()
    execute_result = MagicMock()
    execute_result.all = MagicMock(return_value=[])
    uow.track_features.session.execute = AsyncMock(return_value=execute_result)
    ctx = _ui_ctx()
    result = await ui_camelot_wheel(playlist_id=None, uow=uow, ctx=ctx)
    assert isinstance(result, Column)


@pytest.mark.asyncio
async def test_ui_score_pool_matrix_renders_column_with_empty_pool() -> None:
    from app.tools.ui.score_pool_matrix import ui_score_pool_matrix

    uow = _uow_stub()
    scorer = MagicMock()
    # Minimal score stub with overall and hard_reject attrs
    score = MagicMock(overall=0.5, hard_reject=False)
    scorer.score = MagicMock(return_value=score)
    uow.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock()}
    )
    ctx = _ui_ctx()
    result = await ui_score_pool_matrix(track_ids=[1, 2], uow=uow, scorer=scorer, ctx=ctx)
    assert isinstance(result, Column)


@pytest.mark.asyncio
async def test_ui_transition_score_renders_column() -> None:
    from app.tools.ui.transition_score import ui_transition_score

    uow = _uow_stub()
    feat_a = MagicMock()
    feat_b = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={1: feat_a, 2: feat_b})
    scorer = MagicMock()
    # Score must have the 6 component attrs + overall + hard_reject + reject_reason.
    score = MagicMock(
        bpm=0.8,
        harmonics=0.7,
        energy=0.6,
        bass=0.5,
        drums=0.4,
        vocals=0.3,
        overall=0.65,
        hard_reject=False,
        reject_reason=None,
    )
    scorer.score = MagicMock(return_value=score)
    ctx = _ui_ctx()
    result = await ui_transition_score(
        from_track_id=1,
        to_track_id=2,
        intent=None,
        uow=uow,
        scorer=scorer,
        ctx=ctx,
    )
    assert isinstance(result, Column)


# ── Non-empty rendering paths (Codex review #6) ───────────────────────


@pytest.mark.asyncio
async def test_ui_set_view_renders_with_populated_set() -> None:
    """Exercise the non-empty path: items + tracks + features + transitions."""
    from app.tools.ui.set_view import ui_set_view

    uow = _uow_stub("Populated Set")
    items = [
        MagicMock(sort_index=1, track_id=10),
        MagicMock(sort_index=2, track_id=20),
        MagicMock(sort_index=3, track_id=30),
    ]
    uow.set_versions.get_items = AsyncMock(return_value=items)

    class _Track:
        def __init__(self, title: str) -> None:
            self.title = title

    track_map = {10: _Track("A"), 20: _Track("B"), 30: _Track("C")}
    uow.tracks.get_many = AsyncMock(return_value=track_map)

    feat_map = {
        10: MagicMock(bpm=124.0, key_code=8, integrated_lufs=-9.0, mood="hypnotic"),
        20: MagicMock(bpm=126.0, key_code=8, integrated_lufs=-8.5, mood="driving"),
        30: MagicMock(bpm=128.0, key_code=10, integrated_lufs=-8.0, mood="peak_time"),
    }
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feat_map)

    pair_map = {
        (10, 20): MagicMock(overall_quality=0.78, hard_reject=False),
        (20, 30): MagicMock(overall_quality=0.0, hard_reject=True),  # hard reject path
    }
    uow.transitions.get_pairs_batch = AsyncMock(return_value=pair_map)

    ctx = _ui_ctx()
    result = await ui_set_view(set_id=1, version_id=None, uow=uow, ctx=ctx)
    assert isinstance(result, Column)

    # Batch methods called exactly once each — proves the N+1 fix.
    uow.tracks.get_many.assert_awaited_once_with([10, 20, 30])
    uow.transitions.get_pairs_batch.assert_awaited_once_with([(10, 20), (20, 30)])


@pytest.mark.asyncio
async def test_ui_library_audit_renders_with_violations_and_uses_get_track_ids() -> None:
    """Playlist scope: must use ``get_track_ids`` and surface audit violations."""
    from app.tools.ui.library_audit import ui_library_audit

    uow = _uow_stub()
    uow.playlists.get = AsyncMock(return_value=MagicMock(id=7, name="Test Playlist"))
    uow.playlists.get_track_ids = AsyncMock(return_value=[101, 102])

    class _T:
        def __init__(self, title: str) -> None:
            self.title = title

    uow.tracks.get_many = AsyncMock(return_value={101: _T("Loud"), 102: _T("Slow")})

    # First track passes audit; second track has a low BPM (< 120) — violates.
    feat_pass = MagicMock(
        bpm=128.0,
        integrated_lufs=-9.0,
        true_peak_db=-1.0,
        bpm_confidence=0.9,
        crest_factor_db=10.0,
        hp_ratio=3.0,
        key_confidence=0.8,
        spectral_flatness=0.2,
        variable_tempo=False,
        mood="driving",
    )
    feat_fail = MagicMock(
        bpm=80.0,  # well below techno range
        integrated_lufs=-9.0,
        true_peak_db=-1.0,
        bpm_confidence=0.9,
        crest_factor_db=10.0,
        hp_ratio=3.0,
        key_confidence=0.8,
        spectral_flatness=0.2,
        variable_tempo=False,
        mood="acid",
    )
    uow.track_features.get_scoring_features_batch = AsyncMock(
        return_value={101: feat_pass, 102: feat_fail}
    )

    ctx = _ui_ctx()
    result = await ui_library_audit(playlist_id=7, uow=uow, ctx=ctx)
    assert isinstance(result, Column)

    # Critical regression guard: must call get_track_ids, not the old (missing)
    # get_items accessor which silently returned [].
    uow.playlists.get_track_ids.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_ui_camelot_wheel_uses_get_track_ids_for_playlist_scope() -> None:
    """Same regression guard as library_audit but on the wheel tool."""
    from app.tools.ui.camelot_wheel import ui_camelot_wheel

    uow = _uow_stub()
    uow.playlists.get = AsyncMock(return_value=MagicMock(id=42, name="Pool"))
    uow.playlists.get_track_ids = AsyncMock(return_value=[1, 2, 3])

    execute_result = MagicMock()
    execute_result.all = MagicMock(return_value=[(1, 0), (2, 8), (3, 16)])
    uow.track_features.session.execute = AsyncMock(return_value=execute_result)

    ctx = _ui_ctx()
    result = await ui_camelot_wheel(playlist_id=42, uow=uow, ctx=ctx)
    assert isinstance(result, Column)
    uow.playlists.get_track_ids.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_ui_transition_score_renders_with_hard_reject() -> None:
    """Hard-reject branch must render the REJECT badge + reason card."""
    from app.tools.ui.transition_score import ui_transition_score

    uow = _uow_stub()
    feat_a, feat_b = MagicMock(), MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={1: feat_a, 2: feat_b})
    scorer = MagicMock()
    score = MagicMock(
        bpm=0.0,
        harmonics=0.0,
        energy=0.0,
        bass=0.0,
        drums=0.0,
        vocals=0.0,
        overall=0.0,
        hard_reject=True,
        reject_reason="bpm difference 20.0 > 10",
    )
    scorer.score = MagicMock(return_value=score)
    ctx = _ui_ctx()
    result = await ui_transition_score(
        from_track_id=1, to_track_id=2, intent=None, uow=uow, scorer=scorer, ctx=ctx
    )
    assert isinstance(result, Column)
