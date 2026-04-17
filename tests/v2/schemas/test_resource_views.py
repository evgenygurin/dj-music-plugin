"""Resource view schemas — validate field shape and serialization."""

from __future__ import annotations

import json

from app.v2.schemas.resource_views import (
    BestPairsView,
    PlaylistAuditView,
    SchemaEntityView,
    SchemaIndexView,
    SchemaProviderIndexView,
    SchemaProviderView,
    SessionDraftView,
    SessionEnergyTrendView,
    SessionToolHistoryView,
    SetCheatsheetView,
    SetCompareView,
    SetNarrativeView,
    SetReviewView,
    SetSummaryView,
    SetTracksView,
    SetTransitionsView,
    SuggestNextView,
    SuggestReplacementView,
    TrackAuditView,
    TransitionExplainView,
    TransitionHistoryView,
    TransitionScoreView,
)


def test_track_audit_view_validates() -> None:
    view = TrackAuditView(track_id=1, passed=True, violations=[], score=0.95, criteria_checked=14)
    assert view.track_id == 1
    assert view.passed is True
    dumped = json.loads(view.model_dump_json())
    assert dumped["passed"] is True
    assert dumped["violations"] == []


def test_playlist_audit_view_accepts_items() -> None:
    view = PlaylistAuditView(
        playlist_id=42,
        total_tracks=10,
        passed=8,
        failed=2,
        per_track=[
            {"track_id": 1, "passed": True, "violations": []},
            {"track_id": 2, "passed": False, "violations": ["bpm < 120"]},
        ],
    )
    assert view.total_tracks == 10
    assert view.failed == 2


def test_set_summary_view_fields() -> None:
    view = SetSummaryView(
        set_id=1,
        name="Friday Night",
        template_name="classic_60",
        version_count=3,
        latest_version_id=55,
        latest_quality_score=0.82,
    )
    assert view.latest_quality_score == 0.82


def test_set_cheatsheet_view_has_lines() -> None:
    view = SetCheatsheetView(
        set_id=1,
        version_id=55,
        lines=[
            {"position": 1, "title": "A", "bpm": 124.0, "key": "8A", "energy": -8.2},
            {"position": 2, "title": "B", "bpm": 125.5, "key": "9A", "energy": -7.9},
        ],
    )
    assert len(view.lines) == 2


def test_transition_score_view_components() -> None:
    view = TransitionScoreView(
        from_track_id=1,
        to_track_id=2,
        overall=0.74,
        hard_reject=False,
        reject_reason=None,
        components={
            "bpm": 0.85,
            "harmonic": 0.6,
            "energy": 0.8,
            "spectral": 0.7,
            "groove": 0.72,
            "timbral": 0.65,
        },
    )
    assert view.components["bpm"] == 0.85


def test_transition_score_view_hard_reject() -> None:
    view = TransitionScoreView(
        from_track_id=1,
        to_track_id=2,
        overall=0.0,
        hard_reject=True,
        reject_reason="BPM difference 12.0 > 10",
        components={},
    )
    assert view.hard_reject is True
    assert "12.0" in (view.reject_reason or "")


def test_best_pairs_view_is_list() -> None:
    view = BestPairsView(
        pairs=[
            {"from_track_id": 1, "to_track_id": 2, "plays": 5, "avg_reaction": 4.2},
        ],
        limit=10,
    )
    assert view.limit == 10
    assert view.pairs[0]["plays"] == 5


def test_session_draft_view_empty() -> None:
    view = SessionDraftView(
        session_id="abc",
        tracks=[],
        target_duration_ms=None,
        template_name=None,
        last_mutation_at=None,
    )
    assert view.tracks == []


def test_schema_index_view_lists_entities() -> None:
    view = SchemaIndexView(entities=["track", "playlist", "set"])
    assert "track" in view.entities


def test_schema_entity_view_snapshot() -> None:
    view = SchemaEntityView(
        name="track",
        operations=["list", "get", "create", "update", "delete", "aggregate"],
        presets={"id": ["id"], "summary": ["id", "title", "bpm"]},
        default_preset="id",
        searchable_fields=["title"],
        filterable_fields={"bpm": ["eq", "gte", "lte", "range"]},
        sortable_fields=["bpm", "id", "title"],
        relations=["artists", "features"],
        view_schema={"type": "object"},
        filter_schema={"type": "object"},
        create_schema={"type": "object"},
        update_schema={"type": "object"},
    )
    assert view.name == "track"


def test_suggest_next_view_shape() -> None:
    view = SuggestNextView(
        from_track_id=1,
        limit=5,
        energy_direction="up",
        candidates=[
            {"track_id": 2, "title": "Drop", "score": 0.88, "bpm": 126, "key": "9A"},
        ],
    )
    assert view.energy_direction == "up"


def test_suggest_replacement_view_shape() -> None:
    view = SuggestReplacementView(
        set_id=5,
        position=3,
        removed_track_id=42,
        candidates=[{"track_id": 77, "score": 0.81, "reason": "similar energy + 1 bpm"}],
    )
    assert view.position == 3


def test_session_tool_history_view_shape() -> None:
    view = SessionToolHistoryView(
        session_id="abc",
        entries=[{"tool": "entity_list", "at": "2026-04-17T10:00:00Z", "ok": True}],
    )
    assert view.entries[0]["tool"] == "entity_list"


def test_session_energy_trend_view_shape() -> None:
    view = SessionEnergyTrendView(
        last_n=5,
        samples=[-10.2, -9.8, -9.0, -8.5, -8.0],
    )
    assert len(view.samples) == 5


def test_set_narrative_view_shape() -> None:
    view = SetNarrativeView(
        set_id=1,
        version_id=55,
        narrative="Opens cool, climbs through hypnotic peak, lands soft.",
        phases=[{"label": "warm_up", "start": 0, "end": 3}],
    )
    assert "Opens" in view.narrative


def test_set_review_view_shape() -> None:
    view = SetReviewView(
        set_id=1,
        version_id=55,
        quality_score=0.71,
        weak_transitions=[{"position": 4, "score": 0.3, "reason": "energy gap"}],
        hard_conflicts=[],
    )
    assert view.weak_transitions[0]["position"] == 4


def test_set_compare_view_shape() -> None:
    view = SetCompareView(
        set_id=1,
        version_a={"id": 10, "quality_score": 0.65},
        version_b={"id": 11, "quality_score": 0.78},
        delta=0.13,
        changed_positions=[2, 5, 7],
    )
    assert view.delta == 0.13


def test_transition_explain_view_shape() -> None:
    view = TransitionExplainView(
        from_track_id=1,
        to_track_id=2,
        overall=0.74,
        narrative="Smooth Camelot step, mild energy lift.",
        suggestions=["Use 32-bar bass-swap"],
    )
    assert "Camelot" in view.narrative


def test_transition_history_view_shape() -> None:
    view = TransitionHistoryView(
        limit=20,
        entries=[
            {
                "id": 1,
                "from_track_id": 1,
                "to_track_id": 2,
                "at": "2026-04-17T10:00:00Z",
                "reaction": "hot",
            }
        ],
    )
    assert view.limit == 20


def test_set_tracks_view_shape() -> None:
    view = SetTracksView(
        set_id=1,
        version_id=55,
        tracks=[{"position": 1, "track_id": 10, "title": "A"}],
    )
    assert view.tracks[0]["position"] == 1


def test_set_transitions_view_shape() -> None:
    view = SetTransitionsView(
        set_id=1,
        version_id=55,
        transitions=[{"position": 1, "from_track_id": 10, "to_track_id": 11, "overall": 0.8}],
    )
    assert view.transitions[0]["overall"] == 0.8


def test_schema_provider_index_view() -> None:
    view = SchemaProviderIndexView(providers=["yandex"])
    assert "yandex" in view.providers


def test_schema_provider_view() -> None:
    view = SchemaProviderView(
        name="yandex",
        entities_supported=["track", "album", "artist", "playlist", "likes"],
        operations={"read": True, "write": True, "search": True, "download_audio": True},
    )
    assert view.operations["download_audio"] is True
