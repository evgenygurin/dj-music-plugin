"""Tests for BaseAnalyzer Template Method, @register_analyzer, AnalyzerRegistry."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pytest

from app.audio.analyzers.base import (
    _ANALYZER_REGISTRY,
    AnalyzerRegistry,
    BaseAnalyzer,
    register_analyzer,
)
from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal


@pytest.fixture(autouse=True)
def _clean_registry():
    """Remove test-only entries from global registry after each test.

    Real analyzers (added by @register_analyzer during module import) must survive,
    because importlib won't re-trigger the decorator for already-imported modules.
    Test analyzers use names starting with '_test_' by convention.
    """
    yield
    test_keys = [k for k in _ANALYZER_REGISTRY if k.startswith("_test_")]
    for k in test_keys:
        del _ANALYZER_REGISTRY[k]


def _make_ctx(n_samples: int = 22050) -> AnalysisContext:
    signal = AudioSignal(
        samples=np.random.default_rng(42).standard_normal(n_samples).astype(np.float32),
        sample_rate=22050,
        duration_seconds=n_samples / 22050,
    )
    return AnalysisContext(signal)


class TestBaseAnalyzerTemplateMethod:
    def test_empty_signal_returns_failure(self) -> None:
        @register_analyzer
        class EmptyTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_empty"

            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                return {"value": 1}

        signal = AudioSignal(
            samples=np.array([], dtype=np.float32),
            sample_rate=22050,
            duration_seconds=0.0,
        )
        ctx = AnalysisContext(signal)
        result = EmptyTestAnalyzer().run(ctx)
        assert result.success is False
        assert "Empty signal" in (result.error or "")

    def test_successful_extraction(self) -> None:
        @register_analyzer
        class SuccessTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_success"

            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                return {"bpm": 128.0}

        ctx = _make_ctx()
        result = SuccessTestAnalyzer().run(ctx)
        assert result.success is True
        assert result.features["bpm"] == 128.0
        assert result.analyzer_name == "_test_success"

    def test_exception_in_extract_caught(self) -> None:
        @register_analyzer
        class FailTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_fail"

            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                raise ValueError("deliberate error")

        ctx = _make_ctx()
        result = FailTestAnalyzer().run(ctx)
        assert result.success is False
        assert "deliberate error" in (result.error or "")


class TestRegisterAnalyzerDecorator:
    def test_registers_in_global_dict(self) -> None:
        @register_analyzer
        class RegTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_reg"

            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                return {}

        assert "_test_reg" in _ANALYZER_REGISTRY
        assert _ANALYZER_REGISTRY["_test_reg"] is RegTestAnalyzer


class TestAnalyzerRegistry:
    """NOTE: discover() tests moved to Task 7 — they require @register_analyzer on real analyzers."""

    def test_get_nonexistent_returns_none(self) -> None:
        registry = AnalyzerRegistry()
        assert registry.get("nonexistent") is None

    def test_manual_register(self) -> None:
        @register_analyzer
        class ManualTestAnalyzer(BaseAnalyzer):
            name: ClassVar[str] = "_test_manual"

            def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
                return {"x": 1}

        registry = AnalyzerRegistry()
        registry.register(ManualTestAnalyzer())
        assert registry.get("_test_manual") is not None
        assert registry.list_all() == ["_test_manual"]


@pytest.fixture
def sine_signal() -> AudioSignal:
    t = np.linspace(0, 2.0, int(22050 * 2.0), endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    return AudioSignal(samples=samples, sample_rate=22050, duration_seconds=2.0)


def test_depends_on_default_is_empty():
    """BaseAnalyzer.depends_on defaults to empty frozenset."""

    @register_analyzer
    class NoDepsAnalyzer(BaseAnalyzer):
        name: ClassVar[str] = "_test_no_deps"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []

        def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
            return {"val": 1}

    assert NoDepsAnalyzer.depends_on == frozenset()


def test_run_passes_prior_results_to_dependent_analyzer(sine_signal: AudioSignal):
    """run() passes prior_results to _extract when depends_on is set."""

    @register_analyzer
    class _DepAnalyzer(BaseAnalyzer):
        name: ClassVar[str] = "_test_dep"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []
        depends_on: ClassVar[frozenset[str]] = frozenset({"beat"})

        def _extract(
            self, ctx: AnalysisContext, *, prior_results: dict[str, Any] | None = None
        ) -> dict[str, Any]:
            val = (prior_results or {}).get("beat_times", [])
            return {"got_beats": len(val) > 0}

    analyzer = _DepAnalyzer()
    ctx = AnalysisContext(sine_signal)
    result = analyzer.run(ctx, {"beat_times": [0.5, 1.0, 1.5]})
    assert result.success
    assert result.features["got_beats"] is True


def test_run_does_not_pass_prior_results_to_independent_analyzer(sine_signal: AudioSignal):
    """run() calls _extract(ctx) without prior_results for independent analyzers."""

    @register_analyzer
    class _IndepAnalyzer(BaseAnalyzer):
        name: ClassVar[str] = "_test_indep"
        capabilities: ClassVar[frozenset[str]] = frozenset()
        required_packages: ClassVar[list[str]] = []

        def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
            return {"independent": True}

    analyzer = _IndepAnalyzer()
    ctx = AnalysisContext(sine_signal)
    result = analyzer.run(ctx, {"beat_times": [0.5, 1.0]})  # prior_results ignored
    assert result.success
    assert result.features["independent"] is True


class TestAnalyzerRegistryDiscover:
    """These tests require @register_analyzer on real analyzers (Task 7)."""

    def test_discover_finds_core_analyzers(self) -> None:
        registry = AnalyzerRegistry()
        registry.discover()
        available = registry.list_available()
        assert "loudness" in available
        assert "energy" in available
        assert "spectral" in available
        assert "structure" in available

    def test_get_returns_instance(self) -> None:
        registry = AnalyzerRegistry()
        registry.discover()
        analyzer = registry.get("loudness")
        assert analyzer is not None
        assert analyzer.name == "loudness"

    def test_list_all_includes_optional(self) -> None:
        """If librosa is installed, optional analyzers should be listed."""
        registry = AnalyzerRegistry()
        registry.discover()
        all_names = registry.list_all()
        assert len(all_names) >= 4
