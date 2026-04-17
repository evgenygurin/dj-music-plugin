"""Django-style lookup parser tests."""

import pytest
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.v2.shared.errors import ValidationError
from app.v2.shared.filters import parse_filter, split_lookup


class _Base(DeclarativeBase):
    pass


class _DummyModel(_Base):
    __tablename__ = "_dummy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bpm: Mapped[float] = mapped_column(primary_key=False)
    title: Mapped[str] = mapped_column(String(200))
    mood: Mapped[str | None] = mapped_column(String(30), nullable=True)
    variable: Mapped[bool] = mapped_column(Boolean, default=False)


def test_split_lookup_plain_field() -> None:
    assert split_lookup("bpm") == ("bpm", "eq")


def test_split_lookup_with_operator() -> None:
    assert split_lookup("bpm__gte") == ("bpm", "gte")


def test_split_lookup_multi_underscore_field() -> None:
    assert split_lookup("track_id__in") == ("track_id", "in")


def test_parse_filter_equality() -> None:
    clauses = parse_filter(_DummyModel, {"id": 42})
    assert len(clauses) == 1
    assert "id" in str(clauses[0])


def test_parse_filter_gte_lt() -> None:
    clauses = parse_filter(_DummyModel, {"bpm__gte": 120, "bpm__lt": 155})
    assert len(clauses) == 2


def test_parse_filter_in_list() -> None:
    clauses = parse_filter(_DummyModel, {"mood__in": ["peak_time", "acid"]})
    assert len(clauses) == 1


def test_parse_filter_icontains_wildcards() -> None:
    clauses = parse_filter(_DummyModel, {"title__icontains": "mix"})
    assert len(clauses) == 1


def test_parse_filter_isnull_true() -> None:
    clauses = parse_filter(_DummyModel, {"mood__isnull": True})
    assert len(clauses) == 1


def test_parse_filter_range() -> None:
    clauses = parse_filter(_DummyModel, {"bpm__range": [120.0, 155.0]})
    assert len(clauses) == 1


def test_parse_filter_unknown_field_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse_filter(_DummyModel, {"nonexistent_field": 1})
    assert "nonexistent_field" in str(exc_info.value)


def test_parse_filter_unknown_operator_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        parse_filter(_DummyModel, {"bpm__bogus": 1})
    assert "bogus" in str(exc_info.value)


def test_parse_filter_allowed_fields_whitelist() -> None:
    with pytest.raises(ValidationError):
        parse_filter(_DummyModel, {"title": "Mixdown"}, allowed_fields={"bpm"})


def test_parse_filter_empty_dict_returns_empty() -> None:
    assert parse_filter(_DummyModel, {}) == []
