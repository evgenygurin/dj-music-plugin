"""Tests for Entity-First base schema classes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dj_music.core.constants import SortDir
from dj_music.schemas.base import BaseEntity, BasePagination, BaseSort, BaseValueObject
from dj_music.schemas.track import TrackFilter


class TestBaseEntity:
    def test_from_attributes_works(self) -> None:
        class FakeRow:
            id = 42

        entity = BaseEntity.model_validate(FakeRow())
        assert entity.id == 42

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            BaseEntity(id=1, unexpected_field="boom")  # type: ignore[call-arg]

    def test_default_id(self) -> None:
        entity = BaseEntity()
        assert entity.id == 0


class TestBaseValueObject:
    def test_frozen(self) -> None:
        class MyVO(BaseValueObject):
            value: int = 0

        vo = MyVO(value=5)
        assert vo.value == 5
        # frozen model is immutable — equality by value
        vo2 = MyVO(value=5)
        assert vo == vo2

    def test_frozen_assignment_raises(self) -> None:
        class MyVO(BaseValueObject):
            value: int = 0

        vo = MyVO(value=5)
        with pytest.raises(ValidationError):
            vo.value = 10  # type: ignore[misc]


class TestBasePagination:
    def test_defaults(self) -> None:
        p = BasePagination()
        assert p.limit == 20
        assert p.cursor is None

    def test_limit_bounds(self) -> None:
        with pytest.raises(ValidationError):
            BasePagination(limit=0)
        with pytest.raises(ValidationError):
            BasePagination(limit=101)


class TestBaseSort:
    def test_default_asc(self) -> None:
        s = BaseSort()
        assert s.sort_dir == SortDir.ASC

    def test_desc(self) -> None:
        s = BaseSort(sort_dir=SortDir.DESC)
        assert s.sort_dir == SortDir.DESC


class TestTrackFilter:
    def test_defaults(self) -> None:
        f = TrackFilter()
        assert f.limit == 20
        assert f.cursor is None
        assert f.sort_dir == SortDir.ASC
        assert f.bpm_min is None
        assert f.bpm_max is None

    def test_valid_bpm_range(self) -> None:
        f = TrackFilter(bpm_min=120.0, bpm_max=140.0)
        assert f.bpm_min == 120.0
        assert f.bpm_max == 140.0

    def test_bpm_range_inverted_raises(self) -> None:
        with pytest.raises(ValidationError, match="bpm_min must be <= bpm_max"):
            TrackFilter(bpm_min=140.0, bpm_max=120.0)

    def test_energy_range_inverted_raises(self) -> None:
        with pytest.raises(ValidationError, match="energy_min must be <= energy_max"):
            TrackFilter(energy_min=0.8, energy_max=0.2)

    def test_bpm_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TrackFilter(bpm_min=10.0)  # below 20
        with pytest.raises(ValidationError):
            TrackFilter(bpm_max=400.0)  # above 300

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            TrackFilter(unknown_param="x")  # type: ignore[call-arg]
