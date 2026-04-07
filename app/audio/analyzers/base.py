"""BaseAnalyzer ABC, @register_analyzer decorator, AnalyzerRegistry.

GoF patterns:
    - Template Method: run() handles empty signal guard + error wrapping;
      subclass implements _extract(ctx).
    - Registry: @register_analyzer decorator populates global dict.
      AnalyzerRegistry.discover() uses pkgutil.iter_modules() for auto-scan.
"""

from __future__ import annotations

import contextlib
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AnalyzerResult

logger = logging.getLogger(__name__)

# Global registry populated by @register_analyzer decorator
_ANALYZER_REGISTRY: dict[str, type[BaseAnalyzer]] = {}


def register_analyzer(cls: type[BaseAnalyzer]) -> type[BaseAnalyzer]:
    """Decorator for auto-registration. Pattern: Lhotse @register_extractor."""
    _ANALYZER_REGISTRY[cls.name] = cls
    return cls


class BaseAnalyzer(ABC):
    """Base class for all audio analyzers (Template Method pattern).

    Subclasses implement _extract(ctx) -> dict. The run() method handles:
    - Empty signal guard (eliminates 8 duplicate checks)
    - Exception wrapping into AnalyzerResult
    - Uniform error reporting

    All analyzers are synchronous (CPU-bound). Pipeline dispatches them
    via asyncio.to_thread() for parallelism.
    """

    name: ClassVar[str] = ""
    capabilities: ClassVar[frozenset[str]] = frozenset()
    required_packages: ClassVar[list[str]] = []
    depends_on: ClassVar[frozenset[str]] = frozenset()

    # Maximum audio duration (seconds) this analyzer needs. None = full track.
    # Heavy librosa analyzers (beat, bpm, key, spectral) get a centered clip
    # for ~5x speedup on long techno tracks (5-7 min). Analyzers that depend
    # on the full track (structure, loudness) leave this as None.
    clip_duration_s: ClassVar[float | None] = None

    def run(
        self, ctx: AnalysisContext, prior_results: dict[str, Any] | None = None
    ) -> AnalyzerResult:
        """Template Method — guard + delegate. Synchronous (CPU-bound).

        Called via asyncio.to_thread() by pipeline for parallelism.
        Dependent analyzers (with depends_on) receive prior_results from Phase 1.
        """
        if len(ctx.samples) == 0:
            return AnalyzerResult(analyzer_name=self.name, success=False, error="Empty signal")
        start = time.perf_counter()
        try:
            if self.depends_on:
                features = self._extract(ctx, prior_results=prior_results or {})  # type: ignore[call-arg]
            else:
                features = self._extract(ctx)
            return AnalyzerResult(
                analyzer_name=self.name,
                features=features,
                elapsed_s=time.perf_counter() - start,
            )
        except Exception as e:
            logger.warning("Analyzer %s failed: %s", self.name, e)
            return AnalyzerResult(
                analyzer_name=self.name,
                success=False,
                error=str(e),
                elapsed_s=time.perf_counter() - start,
            )

    @abstractmethod
    def _extract(self, ctx: AnalysisContext) -> dict[str, Any]:
        """Subclass implements. Synchronous — pure computation, no I/O."""
        ...

    def is_available(self) -> bool:
        """Check if required packages are installed."""
        for pkg in self.required_packages:
            try:
                __import__(pkg)
            except ImportError:
                return False
        return True


class AnalyzerRegistry:
    """Registry of available audio analyzers.

    Uses auto-discovery via pkgutil.iter_modules() — new analyzer = one file
    with @register_analyzer decorator. No hardcoded import list.
    """

    def __init__(self) -> None:
        self._analyzers: dict[str, BaseAnalyzer] = {}

    def register(self, analyzer: BaseAnalyzer) -> None:
        """Register an analyzer instance."""
        self._analyzers[analyzer.name] = analyzer

    def get(self, name: str) -> BaseAnalyzer | None:
        """Get analyzer by name."""
        return self._analyzers.get(name)

    def list_available(self) -> list[str]:
        """List names of analyzers whose dependencies are satisfied."""
        return [name for name, a in self._analyzers.items() if a.is_available()]

    def list_all(self) -> list[str]:
        """List all registered analyzer names."""
        return list(self._analyzers.keys())

    def discover(self) -> None:
        """Auto-scan analyzers/ package. No hardcoded imports.

        Wraps each import in try/except to handle optional dependencies
        (librosa-based analyzers: bpm, key, beat, mfcc).
        """
        import importlib
        import pkgutil

        import app.audio.analyzers as pkg

        for info in pkgutil.iter_modules(pkg.__path__):
            if info.name in ("base", "__init__"):
                continue
            with contextlib.suppress(ImportError):
                importlib.import_module(f"app.audio.analyzers.{info.name}")

        for name, cls in _ANALYZER_REGISTRY.items():
            if name in self._analyzers:
                continue
            try:
                instance = cls()
                if instance.is_available():
                    self._analyzers[name] = instance
            except ImportError:
                pass
