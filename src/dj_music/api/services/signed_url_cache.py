"""Cache for YM signed audio URLs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class SignedUrlCache:
    """Time-based cache for YM download URLs."""

    ttl_seconds: float = 300.0
    _entries: dict[str, tuple[float, str]] = field(default_factory=dict)

    def get(self, ym_track_id: str) -> str | None:
        """Return a live cached entry, or ``None`` when missing/expired."""
        now = time.monotonic()
        cached = self._entries.get(ym_track_id)
        if cached is None:
            return None
        expires_at, url = cached
        if expires_at <= now:
            self._entries.pop(ym_track_id, None)
            return None
        return url

    def set(self, ym_track_id: str, signed_url: str) -> None:
        """Store a signed URL."""
        self._entries[ym_track_id] = (time.monotonic() + self.ttl_seconds, signed_url)

    def delete(self, ym_track_id: str) -> None:
        """Remove a single entry (e.g. on upstream failure / expired URL)."""
        self._entries.pop(ym_track_id, None)

    def clear(self) -> None:
        """Clear the cache."""
        self._entries.clear()
