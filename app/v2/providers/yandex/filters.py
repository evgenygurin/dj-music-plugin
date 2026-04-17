"""Yandex track filter: genre whitelist/blacklist + duration + title patterns.

Used by TrackImportHandler and DiscoveryWorkflow prompt — keeps filter
logic isolated from the adapter (so the adapter stays dumb).
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TrackFilter:
    genre_allow: frozenset[str] | None = None
    genre_block: frozenset[str] = field(default_factory=frozenset)
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None
    exclude_title_patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        compiled = tuple(re.compile(p) for p in self.exclude_title_patterns)
        object.__setattr__(self, "_compiled", compiled)

    @classmethod
    def from_params(
        cls,
        *,
        genre_allow: Iterable[str] | None = None,
        genre_block: Iterable[str] | None = None,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
        exclude_patterns: Iterable[str] | None = None,
    ) -> TrackFilter:
        return cls(
            genre_allow=frozenset(genre_allow) if genre_allow else None,
            genre_block=frozenset(genre_block or ()),
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            exclude_title_patterns=tuple(exclude_patterns or ()),
        )

    def matches(self, track: dict[str, Any]) -> bool:
        genre = (track.get("genre") or "").lower()
        if (
            self.genre_allow is not None
            and genre
            and genre not in {g.lower() for g in self.genre_allow}
        ):
            return False
        if genre and genre in {g.lower() for g in self.genre_block}:
            return False
        duration = track.get("duration_ms")
        if duration is not None:
            if self.min_duration_ms is not None and duration < self.min_duration_ms:
                return False
            if self.max_duration_ms is not None and duration > self.max_duration_ms:
                return False
        title = track.get("title") or ""
        return all(not pattern.search(title) for pattern in self._compiled)

    def apply(self, tracks: Collection[dict[str, Any]]) -> list[dict[str, Any]]:
        return [t for t in tracks if self.matches(t)]
