from __future__ import annotations

import hashlib
from pathlib import Path


def cache_directory(
    cache_root: Path, input_path: Path, model: str, pipeline_version: str = "2"
) -> Path:
    """Return a stable result directory while preserving the existing layout."""
    stat = input_path.stat()
    identity = (
        f"{input_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{pipeline_version}".encode()
    )
    digest = hashlib.sha256(identity).hexdigest()[:12]
    return cache_root / f"{input_path.stem}_{digest}" / model / input_path.stem
