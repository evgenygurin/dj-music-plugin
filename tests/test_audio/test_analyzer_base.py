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
    """Save/restore global registry to prevent test pollution."""
    snapshot = dict(_ANALYZER_REGISTRY)
    yield
    _ANALYZER_REGISTRY.clear()
    _ANALYZER_REGISTRY.update(snapshot)


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
