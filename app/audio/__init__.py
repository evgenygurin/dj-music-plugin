"""v2 audio analysis module — layered architecture.

Layers:
    core/       — DSP primitives, types (0 app deps)
    analyzers/  — feature extractors (BaseAnalyzer + registry)
    classification/ — mood/subgenre classifier (Strategy pattern)
    pipeline.py — orchestrator (parallel execution)
"""

from app.audio.analyzers import AnalyzerRegistry, BaseAnalyzer
from app.audio.classification import MoodClassifier, MoodResult
from app.audio.core import (
    AnalysisContext,
    AnalyzerResult,
    AudioLoader,
    AudioSignal,
    FrameParams,
)
from app.audio.level_config import AnalysisLevel, get_analyzers_for_level

__all__ = [
    "AnalysisContext",
    "AnalysisLevel",
    "AnalyzerRegistry",
    "AnalyzerResult",
    "AudioLoader",
    "AudioSignal",
    "BaseAnalyzer",
    "FrameParams",
    "MoodClassifier",
    "MoodResult",
    "get_analyzers_for_level",
]
