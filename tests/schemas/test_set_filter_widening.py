"""Audit iter 12: ``SetFilter`` rejected ``template_name__in``."""

from __future__ import annotations

from app.schemas.set import SetFilter


def test_set_filter_accepts_template_name_in() -> None:
    SetFilter.model_validate({"template_name__in": ["classic_60", "peak_hour_60"]})


def test_set_filter_accepts_source_playlist_id_in() -> None:
    SetFilter.model_validate({"source_playlist_id__in": [1, 2, 3]})


def test_set_filter_accepts_title_alias() -> None:
    SetFilter.model_validate({"title__eq": "QQQ"})
    SetFilter.model_validate({"title__icontains": "qqq"})
