"""File system utilities."""

from __future__ import annotations

from pathlib import Path

from dj_music.core.config import settings


def is_icloud_stub(path: Path) -> bool:
    """Check if a file is an iCloud stub (not fully downloaded).

    iCloud stubs have allocated disk blocks significantly less than
    their reported file size. Threshold from settings.
    """
    try:
        stat = path.stat()
        if stat.st_size == 0:
            return False
        return stat.st_blocks * 512 < stat.st_size * settings.delivery_icloud_stub_threshold
    except (OSError, AttributeError):
        return False
