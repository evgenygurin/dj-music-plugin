"""Tests for AnalyzerRegistry and BaseAnalyzer."""

from __future__ import annotations

from typing import Any, ClassVar

from dj_music.audio.analyzers import AnalyzerRegistry, BaseAnalyzer
from dj_music.audio.core import AudioSignal
from dj_music.audio.core.context import AnalysisContext


class DummyAnalyzer(BaseAnalyzer):
    """Analyzer that always succeeds."""

    name: ClassVar[str] = "dummy"
    capabilities: ClassVar[frozenset[str]] = frozenset({"test"})
    required_packages: ClassVar[list[str]] = []

    def _extract(self, ctx: Any) -> dict[str, Any]:
        return {"value": 42}


class UnavailableAnalyzer(BaseAnalyzer):
    """Analyzer whose dependency is never installed."""

    name: ClassVar[str] = "unavailable"
    capabilities: ClassVar[frozenset[str]] = frozenset({"test"})
    required_packages: ClassVar[list[str]] = ["nonexistent_package_xyz_999"]

    def _extract(self, ctx: Any) -> dict[str, Any]:
        return {}


class TestBaseAnalyzer:
    def test_is_available_no_deps(self) -> None:
        analyzer = DummyAnalyzer()
        assert analyzer.is_available() is True

    def test_is_available_missing_dep(self) -> None:
        analyzer = UnavailableAnalyzer()
        assert analyzer.is_available() is False


class TestAnalyzerRegistry:
    def test_register_and_get(self) -> None:
        registry = AnalyzerRegistry()
        analyzer = DummyAnalyzer()
        registry.register(analyzer)
        assert registry.get("dummy") is analyzer

    def test_get_nonexistent(self) -> None:
        registry = AnalyzerRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all(self) -> None:
        registry = AnalyzerRegistry()
        registry.register(DummyAnalyzer())
        registry.register(UnavailableAnalyzer())
        assert sorted(registry.list_all()) == ["dummy", "unavailable"]

    def test_list_available(self) -> None:
        registry = AnalyzerRegistry()
        registry.register(DummyAnalyzer())
        registry.register(UnavailableAnalyzer())
        assert registry.list_available() == ["dummy"]

    def test_discover(self) -> None:
        registry = AnalyzerRegistry()
        registry.discover()
        all_names = registry.list_all()
        assert "loudness" in all_names
        assert "energy" in all_names
        assert "spectral" in all_names

    def test_discover_all_available(self) -> None:
        """All core analyzers should be available (pure numpy)."""
        registry = AnalyzerRegistry()
        registry.discover()
        available = registry.list_available()
        assert "loudness" in available
        assert "energy" in available
        assert "spectral" in available


class TestDummyAnalyzer:
    def test_run(self) -> None:
        import numpy as np

        analyzer = DummyAnalyzer()
        signal = AudioSignal(
            samples=np.zeros(1000, dtype=np.float32),
            sample_rate=22050,
            duration_seconds=1000 / 22050,
        )
        result = analyzer.run(AnalysisContext(signal))
        assert result.success is True
        assert result.features["value"] == 42
