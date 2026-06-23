"""Temp download utility — download YM track to temp file with auto-cleanup.

v2 port: the YM client dependency is injected at runtime and typed as
``Any`` to keep ``app.audio`` free of legacy imports (no v2 YM
client exists yet; a full port will retype this once ``app.ym``
lands).
"""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any


@asynccontextmanager
async def temp_download_track(
    client: Any,
    ym_track_id: str,
    prefer_bitrate: int = 320,
) -> AsyncIterator[Path]:
    """Download track to temp file, yield path, delete on exit.

    Usage:
        async with temp_download_track(client, "12345") as path:
            features = await pipeline.analyze(str(path))
        # file auto-deleted here
    """
    tmp_dir = tempfile.mkdtemp(prefix="dj_analysis_")
    tmp_path = Path(tmp_dir) / f"{ym_track_id}.mp3"
    try:
        # download_track always picks the highest available bitrate; the
        # prefer_bitrate arg is kept for API compatibility but not forwarded.
        await client.download_track(ym_track_id, tmp_path)
        yield tmp_path
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
        tmp_dir_path = Path(tmp_dir)
        if tmp_dir_path.exists():
            tmp_dir_path.rmdir()
