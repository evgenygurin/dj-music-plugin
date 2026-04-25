"""Error-handling contract for ``BaseAnalyzer.run()``.

Narrow exception catch — we absorb known compute failures
(`ValueError`, `RuntimeError`, `ImportError`, `ArithmeticError`,
`AssertionError`) into ``AnalyzerResult(success=False)`` so a single
broken analyzer cannot abort a full batch. Anything else (especially
``MemoryError`` and OS-level errors delivered as exceptions) must
propagate so the pipeline can decide whether to abort.

Background — a too-broad ``except Exception`` masks numba/numpy ABI
mismatches, OOM precursors, and signal-derived errors. The pipeline
returns partial features → mood classifier returns the wrong subgenre
→ root cause buried for hours.
"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pytest

from app.audio.analyzers.base import BaseAnalyzer
from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SR = 22050


def _ctx() -> AnalysisContext:
    samples = np.zeros(int(SR * 0.5), dtype=np.float32)
    sig = AudioSignal(samples=samples, sample_rate=SR, duration_seconds=0.5)
    return AnalysisContext(sig)


class _RaisingAnalyzer(BaseAnalyzer):
    """Generic shim: raise whatever exception the test injects."""

    name: ClassVar[str] = "_raising"
    capabilities: ClassVar[frozenset[str]] = frozenset()
    required_packages: ClassVar[list[str]] = []

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        raise self._exc


@pytest.mark.parametrize(
    "exc_type",
    [
        ValueError,
        RuntimeError,
        ImportError,
        ArithmeticError,
        AssertionError,
    ],
)
def test_known_compute_failures_become_failed_result(exc_type: type[BaseException]) -> None:
    analyzer = _RaisingAnalyzer(exc_type("boom"))
    result = analyzer.run(_ctx())
    assert result.success is False
    assert result.error == "boom"
    assert result.analyzer_name == "_raising"


def test_memory_error_propagates_not_swallowed() -> None:
    """OOM precursor must surface — pipeline decides whether to abort batch."""
    analyzer = _RaisingAnalyzer(MemoryError("simulated OOM"))
    with pytest.raises(MemoryError, match="simulated OOM"):
        analyzer.run(_ctx())


def test_keyboard_interrupt_propagates() -> None:
    """User interrupt must always reach the loop — never swallowed."""
    analyzer = _RaisingAnalyzer(KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        analyzer.run(_ctx())


def test_system_exit_propagates() -> None:
    """``SystemExit`` is ``BaseException`` — must not be caught either."""
    analyzer = _RaisingAnalyzer(SystemExit(1))
    with pytest.raises(SystemExit):
        analyzer.run(_ctx())


def test_unknown_exception_propagates() -> None:
    """Anything outside the narrow allowlist (e.g. custom ``OSError``)
    must propagate so root cause reaches the operator.
    """

    class _CustomBoomError(Exception):
        pass

    analyzer = _RaisingAnalyzer(_CustomBoomError("unexpected"))
    with pytest.raises(_CustomBoomError, match="unexpected"):
        analyzer.run(_ctx())
