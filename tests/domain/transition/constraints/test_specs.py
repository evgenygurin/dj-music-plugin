"""Tests for hard-constraint specs."""

from __future__ import annotations

from app.domain.transition.constraints.chain import HardConstraintChain
from app.domain.transition.constraints.specs.bpm_difference import BpmDifferenceSpec
from app.domain.transition.constraints.specs.camelot_distance import CamelotDistanceSpec
from app.domain.transition.constraints.specs.energy_gap import EnergyGapSpec
from app.shared.features import TrackFeatures


class TestBpmDifferenceSpec:
    def test_close_bpm_passes(self) -> None:
        spec = BpmDifferenceSpec()
        a = TrackFeatures(bpm=128.0)
        b = TrackFeatures(bpm=130.0)
        assert spec.check(a, b) is None

    def test_pre_computed_dist(self) -> None:
        spec = BpmDifferenceSpec()
        a = TrackFeatures()
        b = TrackFeatures()
        result = spec.check(a, b, pre_bpm_dist=12.0)
        assert result is not None


class TestCamelotDistanceSpec:
    def test_same_key_passes(self) -> None:
        spec = CamelotDistanceSpec()
        a = TrackFeatures(key_code=4)
        b = TrackFeatures(key_code=4)
        assert spec.check(a, b) is None

    def test_pre_computed_dist(self) -> None:
        spec = CamelotDistanceSpec()
        a = TrackFeatures(key_code=0)
        b = TrackFeatures(key_code=0)
        result = spec.check(a, b, pre_key_dist=6)
        assert result is not None

    def test_atonal_no_reject(self) -> None:
        spec = CamelotDistanceSpec()
        a = TrackFeatures(key_code=0, atonality=True)
        b = TrackFeatures(key_code=23, atonality=True)
        assert spec.check(a, b) is None


class TestEnergyGapSpec:
    def test_close_energy_passes(self) -> None:
        spec = EnergyGapSpec()
        a = TrackFeatures(integrated_lufs=-8.0)
        b = TrackFeatures(integrated_lufs=-9.0)
        assert spec.check(a, b) is None

    def test_pre_computed_delta(self) -> None:
        spec = EnergyGapSpec()
        a = TrackFeatures()
        b = TrackFeatures()
        result = spec.check(a, b, pre_energy_delta=10.0)
        assert result is not None


class TestHardConstraintChain:
    def test_chain_passes_close_pair(self) -> None:
        chain = HardConstraintChain((BpmDifferenceSpec(), CamelotDistanceSpec(), EnergyGapSpec()))
        a = TrackFeatures(bpm=128.0, key_code=4, integrated_lufs=-8.0)
        b = TrackFeatures(bpm=130.0, key_code=4, integrated_lufs=-9.0)
        assert chain.check(a, b) is None

    def test_chain_first_fail_stops(self) -> None:
        chain = HardConstraintChain((BpmDifferenceSpec(), CamelotDistanceSpec(), EnergyGapSpec()))
        result = chain.check(TrackFeatures(), TrackFeatures(), pre_bpm_dist=12.0)
        assert result is not None
        assert result.hard_reject is True
        assert result.reject_reason is not None
        assert "BPM" in result.reject_reason
