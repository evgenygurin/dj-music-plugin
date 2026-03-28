"""Backward compatibility — re-exports from new locations.

TODO: Remove after all consumers updated (Task 10).
"""

from app.audio.analyzers.base import AnalyzerRegistry, BaseAnalyzer  # noqa: F401
from app.audio.core.types import AnalyzerResult, AudioSignal  # noqa: F401
