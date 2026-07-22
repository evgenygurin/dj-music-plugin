from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

STEMS_DIR = Path("/Users/laptop/Desktop/Stems")
OUT_DIR = Path("generated-sets/maximal-stem-tool-2026-07-22")
STEM_ORDER: tuple[str, ...] = ("acappella", "bass", "drums", "harmonic", "instrumental")
STEM_PATTERN = re.compile(
    r"^(?P<index>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>[\w-]+)\]\s+"
    r"(?P<title>.+)-(?P<stem>acappella|bass|drums|harmonic|instrumental)\.m4a$"
)


@dataclass(slots=True)
class StemTrack:
    index: int
    title: str
    bpm: float
    genre: str
    stems: dict[str, Path] = field(default_factory=dict)


def complete_tracks(tracks: Iterable[StemTrack]) -> list[StemTrack]:
    required = set(STEM_ORDER)
    return sorted(
        (track for track in tracks if required.issubset(track.stems)),
        key=lambda track: track.index,
    )


def parse_catalog(stems_dir: Path) -> list[StemTrack]:
    if not stems_dir.exists():
        raise FileNotFoundError(f"stems directory does not exist: {stems_dir}")
    if not stems_dir.is_dir():
        raise NotADirectoryError(f"stems path is not a directory: {stems_dir}")

    by_index: dict[int, StemTrack] = {}
    matched = 0
    for path in sorted(stems_dir.glob("*.m4a")):
        match = STEM_PATTERN.match(path.name)
        if match is None:
            continue
        matched += 1
        idx = int(match.group("index"))
        track = by_index.setdefault(
            idx,
            StemTrack(
                index=idx,
                title=match.group("title"),
                bpm=float(match.group("bpm")),
                genre=match.group("genre"),
            ),
        )
        track.stems[match.group("stem")] = path

    if matched == 0:
        raise RuntimeError(f"no prepared stem files matched in {stems_dir}")

    tracks = complete_tracks(by_index.values())
    if not tracks:
        raise RuntimeError(f"no complete five-stem tracks found in {stems_dir}")
    return tracks
