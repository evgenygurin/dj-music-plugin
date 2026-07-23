"""Register all prepared stem files from ``~/Desktop/Stems`` in the library.

Run:
    uv run python scripts/sync_prepared_stem_audio_files.py

The script is idempotent: existing ``dj_library_items.file_path`` rows are left
untouched, and only missing stem files are inserted.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from app.db.session import get_session_factory
from app.domain.render.models import STEM_ORDER
from app.models.audio_file import DjBeatgrid, DjLibraryItem
from app.models.track import Track

STEMS_DIR = Path("/Users/laptop/Desktop/Stems")
STEM_PATTERN = re.compile(
    r"^(?P<index>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>[\w-]+)\]\s+"
    r"(?P<title>.+)-(?P<stem>acappella|bass|drums|harmonic|instrumental)\.m4a$"
)


@dataclass(slots=True)
class PreparedStemTrack:
    index: int
    title: str
    bpm: float
    genre: str
    stems: dict[str, Path] = field(default_factory=dict)


def _hash_head(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        sha.update(fh.read(1_048_576))
    return sha.hexdigest()[:64]


def parse_stem_folder(stems_dir: Path = STEMS_DIR) -> dict[int, PreparedStemTrack]:
    tracks: dict[int, PreparedStemTrack] = {}
    for path in sorted(stems_dir.glob("*.m4a")):
        match = STEM_PATTERN.match(path.name)
        if match is None:
            continue
        idx = int(match.group("index"))
        track = tracks.setdefault(
            idx,
            PreparedStemTrack(
                index=idx,
                title=match.group("title"),
                bpm=float(match.group("bpm")),
                genre=match.group("genre"),
            ),
        )
        track.stems[match.group("stem")] = path
    return tracks


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse stems without writing DB rows",
    )
    args = parser.parse_args()

    parsed = parse_stem_folder()
    complete = [track for track in parsed.values() if set(STEM_ORDER).issubset(track.stems)]
    print(f"Parsed {len(parsed)} stem tracks, {len(complete)} complete 5-stem groups")

    if args.dry_run:
        by_genre: dict[str, int] = {}
        by_bpm: dict[int, int] = {}
        for track in complete:
            by_genre[track.genre] = by_genre.get(track.genre, 0) + 1
            by_bpm[int(track.bpm)] = by_bpm.get(int(track.bpm), 0) + 1
        print(f"Genres: {dict(sorted(by_genre.items()))}")
        print(f"BPM range: {min(by_bpm)}-{max(by_bpm)}" if by_bpm else "BPM range: n/a")
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        title_rows = await session.execute(select(Track.id, Track.title))
        title_to_id = {row.title.lower(): row.id for row in title_rows}

        existing_rows = await session.execute(select(DjLibraryItem.file_path))
        existing_paths = {row.file_path for row in existing_rows}

        created_items = 0
        created_grids = 0
        missing_tracks: list[str] = []
        incomplete: list[str] = []

        for stem_track in complete:
            track_id = title_to_id.get(stem_track.title.lower())
            if track_id is None:
                missing_tracks.append(stem_track.title)
                continue

            missing_stems = set(STEM_ORDER) - set(stem_track.stems)
            if missing_stems:
                label = f"{stem_track.index:04d} {stem_track.title}"
                incomplete.append(f"{label}: {sorted(missing_stems)}")
                continue

            for stem in STEM_ORDER:
                path = stem_track.stems[stem]
                path_str = str(path)
                if path_str in existing_paths:
                    continue
                item = DjLibraryItem(
                    track_id=track_id,
                    file_path=path_str,
                    file_uri=path.as_uri(),
                    file_hash=_hash_head(path),
                    file_size=os.path.getsize(path),
                    mime_type="audio/mp4",
                    source_app=f"prepared_stem:{stem}",
                )
                session.add(item)
                await session.flush()
                session.add(
                    DjBeatgrid(
                        library_item_id=item.id,
                        bpm=stem_track.bpm,
                        first_downbeat_ms=0.0,
                        grid_offset_ms=0.0,
                        confidence=0.95,
                        variable_tempo=False,
                        canonical=(stem == "instrumental"),
                    )
                )
                existing_paths.add(path_str)
                created_items += 1
                created_grids += 1

        await session.commit()

    print(f"Created {created_items} dj_library_items and {created_grids} beatgrids")
    if missing_tracks:
        print(f"Tracks missing in DB by title: {len(missing_tracks)}")
        for title in missing_tracks[:20]:
            print(f"  - {title}")
    if incomplete:
        print(f"Incomplete stem groups skipped: {len(incomplete)}")
        for item in incomplete[:20]:
            print(f"  - {item}")


if __name__ == "__main__":
    asyncio.run(main())
