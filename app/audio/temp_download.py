"""Temp download utility — download track to temp file with auto-cleanup."""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.protocol import MusicProvider


@asynccontextmanager
async def temp_download_track(
    client: MusicProvider,
    track_id: str,
) -> AsyncIterator[Path]:
    """Download track to temp file, yield path, delete on exit.

    Usage:
        async with temp_download_track(provider, "12345") as path:
            features = await pipeline.analyze(str(path))
        # file auto-deleted here
    """
    tmp_dir = tempfile.mkdtemp(prefix="dj_analysis_")
    tmp_path = Path(tmp_dir) / f"{track_id}.mp3"
    try:
        await client.download_track(track_id, tmp_path)
        yield tmp_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
        tmp_dir_path = Path(tmp_dir)
        if tmp_dir_path.exists():
            tmp_dir_path.rmdir()
