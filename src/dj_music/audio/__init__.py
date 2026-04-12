"""Audio analysis module — layered architecture.

Layers:
    core/       — DSP primitives, types (0 app deps)
    analyzers/  — feature extractors (BaseAnalyzer + registry)
    classification/ — mood/subgenre classifier (Strategy pattern)
    pipeline.py — orchestrator (parallel execution)
"""

from dj_music.audio.analyzers import AnalyzerRegistry, BaseAnalyzer
from dj_music.audio.classification import MoodClassifier, MoodResult
from dj_music.audio.core import AnalysisContext, AnalyzerResult, AudioLoader, AudioSignal, FrameParams

__all__ = [
    "AnalysisContext",
    "AnalyzerRegistry",
    "AnalyzerResult",
    "AudioLoader",
    "AudioSignal",
    "BaseAnalyzer",
    "FrameParams",
    "MoodClassifier",
    "MoodResult",
]
