from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from app.audio.analyzers import AnalyzerRegistry
from app.audio.core.loader import AudioLoader
from app.audio.level_config import AnalysisLevel, get_analyzers_for_level
from app.audio.pipeline import AnalysisPipeline


def _make_pipeline() -> AnalysisPipeline:
    registry = AnalyzerRegistry()
    registry.discover()
    return AnalysisPipeline(registry, loader=AudioLoader())


async def analyze_stems(
    stem_paths: dict[str, Path],
    original_path: Path,
) -> dict[str, dict[str, Any]]:
    all_paths: dict[str, Path] = {"original": original_path, **stem_paths}
    pipeline = _make_pipeline()
    analyzers = get_analyzers_for_level(AnalysisLevel(6))

    async def _analyze_one(stem_name: str, path: Path) -> tuple[str, dict[str, Any]]:
        result = await pipeline.analyze(str(path), analyzers=analyzers)
        return stem_name, result.features

    tasks = [_analyze_one(name, path) for name, path in all_paths.items()]
    pairs = await asyncio.gather(*tasks)
    return dict(pairs)
