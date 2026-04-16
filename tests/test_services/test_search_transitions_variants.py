"""Exhaustive branch tests for ``SetScoringService.search_transitions``.

Covers pagination, all filter operators, sort tokens, projection macros,
``include_stats``, and validation errors declared in ``scoring.py``.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track
from app.db.models.transition import Transition
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.transition import TransitionRepository
from app.schemas.tool_output import SearchTransitionsResult
from app.services.set.scoring import SetScoringService


def _svc(db: AsyncSession) -> SetScoringService:
    return SetScoringService(
        set_repo=SetRepository(db),
        feature_repo=FeatureRepository(db),
        transition_repo=TransitionRepository(db),
    )


def _feat(tid: int, **kw: object) -> TrackAudioFeaturesComputed:
    base: dict[str, object] = {
        "track_id": tid,
        "bpm": 128.0,
        "bpm_stability": 0.9,
        "key_code": 8,
        "integrated_lufs": -10.0,
        "analysis_level": 2,
    }
    base.update(kw)
    return TrackAudioFeaturesComputed(**base)


async def _seed_three_transitions(db: AsyncSession) -> tuple[int, int, int]:
    """Three tracks, three transitions (cycle), deterministic scores/moods."""
    t1 = Track(title="AcidLine", duration_ms=300_000, status=0)
    t2 = Track(title="DetroitLine", duration_ms=300_000, status=0)
    t3 = Track(title="BetaTest", duration_ms=300_000, status=0)
    db.add_all([t1, t2, t3])
    await db.flush()

    db.add_all(
        [
            _feat(t1.id, bpm=120.0, mood="acid"),
            _feat(t2.id, bpm=130.0, mood="detroit"),
            _feat(t3.id, bpm=125.0, mood="acid"),
        ]
    )
    await db.flush()

    db.add_all(
        [
            Transition(
                from_track_id=t1.id,
                to_track_id=t2.id,
                overall_quality=0.9,
                hard_reject=False,
                bpm_score=0.8,
                harmonic_score=0.7,
                energy_score=0.6,
                spectral_score=0.5,
                groove_score=0.4,
                timbral_score=0.3,
                fx_type=None,
                overlap_ms=None,
            ),
            Transition(
                from_track_id=t2.id,
                to_track_id=t3.id,
                overall_quality=0.1,
                hard_reject=True,
                bpm_score=0.0,
                harmonic_score=0.0,
                energy_score=0.0,
                spectral_score=0.0,
                groove_score=0.0,
                timbral_score=0.0,
                fx_type="fade",
                overlap_ms=100,
            ),
            Transition(
                from_track_id=t3.id,
                to_track_id=t1.id,
                overall_quality=0.55,
                hard_reject=False,
                bpm_score=0.5,
                harmonic_score=0.5,
                energy_score=0.5,
                spectral_score=0.5,
                groove_score=0.5,
                timbral_score=0.5,
                fx_type=None,
                overlap_ms=None,
            ),
        ]
    )
    await db.flush()
    return t1.id, t2.id, t3.id


@pytest.mark.asyncio
async def test_default_projection_and_stats_toggle(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    r = await svc.search_transitions(limit=10, include_stats=False)
    assert r["total"] == 3
    assert all(set(row) == {"id"} for row in r["rows"])
    assert r["stats"] is None
    assert r["fields"]["selected"] == ["id"]
    assert set(r["fields"]) == {"selected", "excluded"}
    assert "filter_operators" not in r

    r2 = await svc.search_transitions(limit=10, include_stats=True)
    assert r2["stats"] is not None
    assert r2["stats"]["total_rows"] == 3
    assert "component_averages" in r2["stats"]
    SearchTransitionsResult.model_validate(r)
    SearchTransitionsResult.model_validate(r2)


@pytest.mark.asyncio
async def test_field_catalog_toggle(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)
    slim = await svc.search_transitions(limit=1, include_field_catalog=False)
    assert set(slim["fields"]) == {"selected", "excluded"}
    assert "filter_operators" not in slim

    full = await svc.search_transitions(limit=1, include_field_catalog=True)
    assert "available" in full["fields"] and full["fields"]["available"]
    assert "groups" in full["fields"]
    assert "include_macros" in full["fields"]
    assert "filter_operators" in full
    SearchTransitionsResult.model_validate(slim)
    SearchTransitionsResult.model_validate(full)


@pytest.mark.asyncio
async def test_pagination_and_truncation_flags(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    p0 = await svc.search_transitions(limit=1, offset=0, sort_by="id", sort_order="asc")
    assert p0["returned"] == 1
    assert p0["truncated"] is True
    assert p0["next_offset"] == 1

    p1 = await svc.search_transitions(limit=1, offset=1, sort_by="id", sort_order="asc")
    assert p1["offset"] == 1
    assert p1["next_offset"] == 2

    p2 = await svc.search_transitions(limit=1, offset=2, sort_by="id", sort_order="asc")
    assert p2["next_offset"] is None
    assert p2["truncated"] is False


@pytest.mark.asyncio
async def test_sort_multi_tokens_plus_minus_and_id_tiebreak(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    r = await svc.search_transitions(
        limit=10,
        sort_by="+from_bpm,-overall_quality",
        include_fields=["id", "from_bpm", "overall_quality"],
    )
    spec = r["sort"]
    assert spec[0] == {"field": "from_bpm", "direction": "asc"}
    assert spec[1] == {"field": "overall_quality", "direction": "desc"}
    assert spec[-1]["field"] == "id"


@pytest.mark.asyncio
async def test_sort_direction_overrides_sort_order(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    r = await svc.search_transitions(
        limit=1,
        sort_by="from_bpm",
        sort_order="desc",
        sort_direction="asc",
        include_fields=["from_bpm"],
    )
    assert r["sort"][0]["direction"] == "asc"


@pytest.mark.asyncio
async def test_filters_shorthand_eq_and_boolean(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    r = await svc.search_transitions(
        filters={"hard_reject": False},
        include_fields=["id", "hard_reject"],
    )
    assert {row["hard_reject"] for row in r["rows"]} == {False}
    assert r["total"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filters,expect_ids",
    [
        ({"overall_quality": {"eq": 0.9}}, 1),
        ({"overall_quality": {"ne": 0.9}}, 2),
        ({"overall_quality": {"gt": 0.5}}, 2),
        ({"overall_quality": {"gte": 0.9}}, 1),
        ({"overall_quality": {"lt": 0.2}}, 1),
        ({"overall_quality": {"lt": 0.05}}, 0),
        ({"overall_quality": {"lte": 0.1}}, 1),
    ],
)
async def test_filters_numeric_ops(
    db: AsyncSession, filters: dict[str, Any], expect_ids: int
) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)
    r = await svc.search_transitions(filters=filters, include_fields=["id", "overall_quality"])
    assert r["total"] == expect_ids


@pytest.mark.asyncio
async def test_filters_in_not_in_contains(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    r_in = await svc.search_transitions(
        filters={"from_mood": {"in": ["acid", "breakbeat"]}},
        include_fields=["id", "from_mood"],
    )
    assert r_in["total"] == 2
    assert {row["from_mood"] for row in r_in["rows"]} <= {"acid", "breakbeat", None}

    r_not = await svc.search_transitions(
        filters={"from_mood": {"not_in": ["acid"]}},
        include_fields=["id", "from_mood"],
    )
    assert all(row["from_mood"] != "acid" for row in r_not["rows"])

    r_like = await svc.search_transitions(
        filters={"from_title": {"contains": "Line"}},
        include_fields=["id", "from_title"],
    )
    assert r_like["total"] == 2
    assert all("Line" in (row["from_title"] or "") for row in r_like["rows"])


@pytest.mark.asyncio
async def test_filters_is_null_and_overlap(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    r_null = await svc.search_transitions(
        filters={"fx_type": {"is_null": True}},
        include_fields=["id", "fx_type"],
    )
    assert all(row["fx_type"] is None for row in r_null["rows"])
    assert r_null["total"] == 2

    r_not_null = await svc.search_transitions(
        filters={"overlap_ms": {"is_null": False}},
        include_fields=["id", "overlap_ms"],
    )
    assert all(row["overlap_ms"] is not None for row in r_not_null["rows"])
    assert r_not_null["total"] == 1


@pytest.mark.asyncio
async def test_include_macros_and_exclude(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    r_all = await svc.search_transitions(limit=1, include_fields=["all"])
    assert len(r_all["rows"][0]) > 30

    r_tr = await svc.search_transitions(limit=1, include_fields=["transition_fields"])
    keys = set(r_tr["rows"][0])
    assert "from_track_id" in keys and "overall_quality" in keys

    r_ex = await svc.search_transitions(
        limit=1,
        include_fields=["transition_fields"],
        exclude_fields=["transition_recipe_json", "reject_reason"],
    )
    k = set(r_ex["rows"][0])
    assert "transition_recipe_json" not in k
    assert "id" in k


@pytest.mark.asyncio
async def test_include_track_and_feature_macros(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    r_track = await svc.search_transitions(limit=1, include_fields=["track_fields"])
    keys = set(r_track["rows"][0])
    assert "from_track_title" in keys and "to_track_id" in keys

    r_feat = await svc.search_transitions(limit=1, include_fields=["feature_fields"])
    keys_f = set(r_feat["rows"][0])
    assert "from_bpm" in keys_f and "to_mood" in keys_f


@pytest.mark.asyncio
async def test_validation_errors(db: AsyncSession) -> None:
    await _seed_three_transitions(db)
    svc = _svc(db)

    with pytest.raises(ValidationError, match="limit"):
        await svc.search_transitions(limit=0)

    with pytest.raises(ValidationError, match="offset"):
        await svc.search_transitions(offset=-1)

    with pytest.raises(ValidationError, match="sort_by cannot be empty"):
        await svc.search_transitions(sort_by="  ,  ")

    with pytest.raises(ValidationError, match="Unknown sort field"):
        await svc.search_transitions(sort_by="no_such_column")

    with pytest.raises(ValidationError, match="Unknown filter field"):
        await svc.search_transitions(filters={"nope": 1})

    with pytest.raises(ValidationError, match="Unknown include_fields"):
        await svc.search_transitions(include_fields=["nope"])

    with pytest.raises(ValidationError, match="Unknown exclude_fields"):
        await svc.search_transitions(include_fields=["id"], exclude_fields=["nope"])

    with pytest.raises(ValidationError, match="No output fields left"):
        await svc.search_transitions(include_fields=["id"], exclude_fields=["id"])

    with pytest.raises(ValidationError, match="cannot be empty"):
        await svc.search_transitions(filters={"from_track_id": {"in": []}})

    with pytest.raises(ValidationError, match="cannot be empty"):
        await svc.search_transitions(filters={"from_track_id": {"not_in": []}})

    with pytest.raises(ValidationError, match="must be list"):
        await svc.search_transitions(filters={"from_track_id": {"in": "not-a-seq"}})

    with pytest.raises(ValidationError, match="must be list"):
        await svc.search_transitions(filters={"from_track_id": {"not_in": 123}})

    with pytest.raises(ValidationError, match="Unknown operator"):
        await svc.search_transitions(filters={"id": {"bogus": 1}})

    with pytest.raises(ValidationError, match="contains requires"):
        await svc.search_transitions(filters={"from_title": {"contains": None}})

    with pytest.raises(ValidationError, match="is_null must be boolean"):
        await svc.search_transitions(filters={"fx_type": {"is_null": "yes"}})

    with pytest.raises(ValidationError, match="filters must be an object"):
        await svc.search_transitions(filters="not-a-dict")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_filters_non_dict_inner_skipped(db: AsyncSession) -> None:
    """Empty operator dict on a field is ignored (no clause)."""
    await _seed_three_transitions(db)
    svc = _svc(db)
    r = await svc.search_transitions(
        filters={"hard_reject": {}},
        include_fields=["id"],
    )
    assert r["total"] == 3
