"""Regression: ``SetView`` declared ``target_bpm_min/max`` as ``int`` while
``dj_sets`` stores them as FLOAT (a template-derived value such as 124.8).

Live confirmation (set #71, template ``classic_60``):

    entity_list(set, fields=...) / entity_get(set, 71) / ui_set_view(74)
    -> internal error: 2 validation errors for SetView
       target_bpm_min  Input should be a valid integer, got a number
       with a fractional part [type=int_from_float, input_value=124.8]

Any set carrying a fractional target BPM made the whole ``entity_list
(set)`` page (it validates every row) and the UI dashboards raise. The
read-only projection must reflect what is persisted, so the annotation
was widened to ``float``. ``SetCreate`` / ``SetUpdate`` keep the ``int``
input contract — only the View is widened.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.schemas.set import SetView


class TestSetViewFloatBpm:
    def test_fractional_bpm_from_payload_accepted(self) -> None:
        view = SetView.model_validate(
            {
                "id": 71,
                "name": "Driving Techno — Build to Peak",
                "target_bpm_min": 124.8,
                "target_bpm_max": 130.8,
            }
        )
        assert view.target_bpm_min == 124.8
        assert view.target_bpm_max == 130.8

    def test_fractional_bpm_from_orm_attributes_accepted(self) -> None:
        """``from_attributes=True`` path — what the repository actually
        feeds in (a SQLAlchemy row with FLOAT columns)."""
        row = SimpleNamespace(
            id=71,
            name="Driving Techno — Build to Peak",
            description=None,
            target_duration_ms=None,
            target_bpm_min=124.8,
            target_bpm_max=130.8,
            template_name="classic_60",
            source_playlist_id=None,
            version_count=1,
        )
        view = SetView.model_validate(row)
        assert view.target_bpm_min == 124.8
        assert view.target_bpm_max == 130.8

    def test_integer_bpm_still_accepted(self) -> None:
        """Whole-number target BPM (the common case) keeps working."""
        view = SetView.model_validate(
            {"id": 1, "name": "T", "target_bpm_min": 126, "target_bpm_max": 134}
        )
        assert view.target_bpm_min == 126
        assert view.target_bpm_max == 134

    def test_null_bpm_accepted(self) -> None:
        view = SetView.model_validate({"id": 1, "name": "T"})
        assert view.target_bpm_min is None
        assert view.target_bpm_max is None
