"""Prefab Apps previews with demo data.

Standalone PrefabApp instances — one per UI tool — built with seeded
fake data so we can export them to static HTML via ``prefab export``
and screenshot them without a running MCP server or Supabase.

Demo data is representative but synthetic: a fake techno set, a fake
transition pair, mock audit results, etc. None of this touches the DB.
"""

from __future__ import annotations

import asyncio
import itertools
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from prefab_ui import PrefabApp

# --- Demo data ---------------------------------------------------------

DEMO_SET_NAME = "Peak Hour — Warehouse 04"
DEMO_TEMPLATE = "peak_hour_60"

DEMO_TRACKS = [
    {
        "id": 101,
        "title": "Echoes of the Void",
        "bpm": 124.0,
        "key_code": 16,
        "lufs": -9.2,
        "mood": "hypnotic",
    },
    {
        "id": 102,
        "title": "Neon Monolith",
        "bpm": 126.0,
        "key_code": 16,
        "lufs": -8.6,
        "mood": "driving",
    },
    {
        "id": 103,
        "title": "Subterranean Pulse",
        "bpm": 128.0,
        "key_code": 18,
        "lufs": -8.1,
        "mood": "peak_time",
    },
    {
        "id": 104,
        "title": "Iron Cathedral",
        "bpm": 130.0,
        "key_code": 18,
        "lufs": -7.4,
        "mood": "industrial",
    },
    {
        "id": 105,
        "title": "Steel Rain",
        "bpm": 132.0,
        "key_code": 20,
        "lufs": -7.0,
        "mood": "industrial",
    },
    {"id": 106, "title": "Acid Tide", "bpm": 134.0, "key_code": 20, "lufs": -6.5, "mood": "acid"},
    {
        "id": 107,
        "title": "Venom Line",
        "bpm": 136.0,
        "key_code": 22,
        "lufs": -6.1,
        "mood": "hard_techno",
    },
    {
        "id": 108,
        "title": "Arc of Fire",
        "bpm": 138.0,
        "key_code": 22,
        "lufs": -5.8,
        "mood": "hard_techno",
    },
]

DEMO_TRANSITION_SCORES = [0.78, 0.82, 0.71, 0.85, 0.88, 0.62, 0.79]


def _uow_for_set() -> MagicMock:
    uow = MagicMock()

    class _Set:
        id = 1
        name = DEMO_SET_NAME
        template_name = DEMO_TEMPLATE

    class _Version:
        id = 42
        set_id = 1
        quality_score = 0.81

    def _item(i, t):
        m = MagicMock()
        m.sort_index = i + 1
        m.track_id = t["id"]
        return m

    def _track(t):
        class _T:
            pass

        _T.title = t["title"]
        return _T

    from app.domain.transition.features import TrackFeatures

    def _features(t: dict[str, Any]) -> TrackFeatures:
        # ``TrackFeatures`` now carries every field the audit rules inspect
        # (``true_peak_db`` added in response to Codex PR #113 P1). No
        # wrapper needed — the production type is audit-compatible.
        return TrackFeatures(
            bpm=t["bpm"],
            key_code=t["key_code"],
            integrated_lufs=t["lufs"],
            energy_mean=0.18,
            onset_rate=2.4,
            kick_prominence=0.12,
            pulse_clarity=0.08,
            hp_ratio=3.2,
            spectral_centroid_hz=3400.0,
            spectral_flatness=0.18,
            bpm_stability=0.92,
            bpm_confidence=0.88,
            key_confidence=0.82,
            crest_factor_db=11.5,
            loudness_range_lu=7.0,
            hnr_db=-8.5,
            true_peak_db=-1.0,
            variable_tempo=False,
            mood=t["mood"],
        )

    feats = {t["id"]: _features(t) for t in DEMO_TRACKS}
    items = [_item(i, t) for i, t in enumerate(DEMO_TRACKS)]
    tracks_by_id = {t["id"]: _track(t) for t in DEMO_TRACKS}

    uow.sets = MagicMock()
    uow.sets.get = AsyncMock(return_value=_Set())
    uow.set_versions = MagicMock()
    uow.set_versions.get_latest = AsyncMock(return_value=_Version())
    uow.set_versions.get_items = AsyncMock(return_value=items)
    uow.set_versions.get = AsyncMock(return_value=_Version())
    uow.tracks = MagicMock()
    uow.tracks.get = AsyncMock(side_effect=lambda tid: tracks_by_id.get(tid))
    uow.tracks.get_many = AsyncMock(return_value=tracks_by_id)
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)

    # Transition stubs — match pairwise
    pairs = list(itertools.pairwise(t["id"] for t in DEMO_TRACKS))
    transition_map: dict[tuple[int, int], MagicMock] = {}
    for (a, b), s in zip(pairs, DEMO_TRANSITION_SCORES, strict=False):
        m = MagicMock()
        m.overall_quality = s
        m.hard_reject = False
        m.from_track_id = a
        m.to_track_id = b
        transition_map[(a, b)] = m

    uow.transitions = MagicMock()
    uow.transitions.get_by_pair = AsyncMock(side_effect=lambda a, b: transition_map.get((a, b)))
    uow.transitions.get_pair = AsyncMock(side_effect=lambda a, b: transition_map.get((a, b)))
    uow.transitions.get_pairs_batch = AsyncMock(return_value=transition_map)
    return uow


def _ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.client_supports_extension = MagicMock(return_value=True)
    return ctx


# --- Build each app ----------------------------------------------------


def _build_set_view_app() -> PrefabApp:
    from app.tools.ui.set_view import ui_set_view

    uow = _uow_for_set()
    ctx = _ctx()
    view = asyncio.run(ui_set_view(set_id=1, version_id=None, uow=uow, ctx=ctx))
    return PrefabApp(view=view, title="ui_set_view — Peak Hour demo")


def _build_transition_score_app() -> PrefabApp:
    from app.tools.ui.transition_score import ui_transition_score

    uow = _uow_for_set()
    scorer = MagicMock()
    score = MagicMock(
        bpm=0.88,
        harmonic=0.72,
        energy=0.81,
        spectral=0.69,
        groove=0.77,
        timbral=0.74,
        overall=0.77,
        hard_reject=False,
        reject_reason=None,
    )
    scorer.score = MagicMock(return_value=score)
    ctx = _ctx()
    view = asyncio.run(
        ui_transition_score(
            from_track_id=103, to_track_id=104, intent=None, uow=uow, scorer=scorer, ctx=ctx
        )
    )
    return PrefabApp(view=view, title="ui_transition_score — Subterranean Pulse → Iron Cathedral")


def _build_library_audit_app() -> PrefabApp:
    from app.tools.ui.library_audit import ui_library_audit

    uow = _uow_for_set()
    # playlist-scope path; stub playlist via the real ``get_track_ids`` accessor
    uow.playlists = MagicMock()
    uow.playlists.get = AsyncMock(return_value=MagicMock(id=7, name="Peak Hour Pool"))
    uow.playlists.get_track_ids = AsyncMock(return_value=[t["id"] for t in DEMO_TRACKS])
    ctx = _ctx()
    view = asyncio.run(ui_library_audit(playlist_id=7, uow=uow, ctx=ctx))
    return PrefabApp(view=view, title="ui_library_audit — Peak Hour Pool")


def _build_score_pool_matrix_app() -> PrefabApp:
    from app.tools.ui.score_pool_matrix import ui_score_pool_matrix

    uow = _uow_for_set()
    ids = [t["id"] for t in DEMO_TRACKS[:5]]
    feats = {tid: MagicMock() for tid in ids}
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value=feats)

    scorer = MagicMock()
    call_count = {"n": 0}
    heat = [
        0.78,
        0.63,
        0.85,
        0.42,
        0.91,
        0.55,
        0.77,
        0.71,
        0.88,
        0.38,
        0.83,
        0.67,
        0.74,
        0.49,
        0.92,
    ]

    def _score(a, b):
        idx = call_count["n"] % len(heat)
        call_count["n"] += 1
        val = heat[idx]
        m = MagicMock()
        m.overall = val
        m.hard_reject = val < 0.4
        return m

    scorer.score = MagicMock(side_effect=_score)
    ctx = _ctx()
    view = asyncio.run(ui_score_pool_matrix(track_ids=ids, uow=uow, scorer=scorer, ctx=ctx))
    return PrefabApp(view=view, title="ui_score_pool_matrix — 5-track heatmap")


def _build_library_dashboard_app() -> PrefabApp:
    from app.tools.ui.library_dashboard import ui_library_dashboard

    uow = _uow_for_set()
    uow.tracks.count = AsyncMock(return_value=23929)
    uow.track_features.count = AsyncMock(return_value=23768)

    # session.execute must return list of (bpm, key_code, mood) tuples
    synthetic_rows = []
    for t in DEMO_TRACKS * 1200:  # ~9.6k rows
        synthetic_rows.append((t["bpm"], t["key_code"], t["mood"]))

    exec_result = MagicMock()
    exec_result.all = MagicMock(return_value=synthetic_rows)
    uow.track_features.session = MagicMock()
    uow.track_features.session.execute = AsyncMock(return_value=exec_result)

    ctx = _ctx()
    view = asyncio.run(ui_library_dashboard(uow=uow, ctx=ctx))
    return PrefabApp(view=view, title="ui_library_dashboard — live library snapshot")


def _build_camelot_wheel_app() -> PrefabApp:
    from app.tools.ui.camelot_wheel import ui_camelot_wheel

    uow = _uow_for_set()
    # scope: library (playlist_id=None). _track_ids_for_scope uses uow.tracks.filter.
    page = MagicMock()
    page.items = [MagicMock(id=t["id"]) for t in DEMO_TRACKS]
    uow.tracks.filter = AsyncMock(return_value=page)
    # rows: (track_id, key_code) for each track
    rows = [(t["id"], t["key_code"]) for t in DEMO_TRACKS]
    exec_result = MagicMock()
    exec_result.all = MagicMock(return_value=rows)
    uow.track_features.session = MagicMock()
    uow.track_features.session.execute = AsyncMock(return_value=exec_result)
    ctx = _ctx()
    view = asyncio.run(ui_camelot_wheel(playlist_id=None, uow=uow, ctx=ctx))
    return PrefabApp(view=view, title="ui_camelot_wheel — demo library")


# --- Export handles (one PrefabApp per module global) ------------------

set_view_app = _build_set_view_app()
transition_score_app = _build_transition_score_app()
library_audit_app = _build_library_audit_app()
score_pool_matrix_app = _build_score_pool_matrix_app()
library_dashboard_app = _build_library_dashboard_app()
camelot_wheel_app = _build_camelot_wheel_app()
