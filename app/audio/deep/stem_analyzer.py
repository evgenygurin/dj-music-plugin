from __future__ import annotations

from pathlib import Path
from typing import Any

from app.audio.pipeline import run_pipeline
from app.repositories.unit_of_work import UnitOfWork


async def analyze_stems(
    uow: UnitOfWork,
    track_id: int,
    stem_paths: dict[str, Path],
    original_path: Path,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    all_paths: dict[str, Path] = {"original": original_path, **stem_paths}

    for stem_name, path in all_paths.items():
        features = await run_pipeline(uow, track_id, path, level=6)
        results[stem_name] = features

    return results
