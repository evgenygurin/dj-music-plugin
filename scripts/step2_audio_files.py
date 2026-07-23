"""Step 2: Create DjLibraryItem + DjBeatgrid for instrumental stems.

Run: uv run python scripts/build_stems_set.py --step2
"""
import asyncio
import hashlib
import os
import re
import sys
from pathlib import Path

from app.db.session import get_session_factory
from app.models.audio_file import DjBeatgrid, DjLibraryItem
from app.repositories.unit_of_work import UnitOfWork

STEMS_DIR = Path("/Users/laptop/Desktop/Stems")
PATTERN = re.compile(
    r"^(?P<index>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>\w+)\]\s+(?P<title>.+?)-(?P<stem>\w+)\.m4a$"
)

# Track IDs from step 1
CANDIDATE_IDS = [161,164,172,173,180,184,214,263,291,313,451,551,554,562,592,686,29581,29582,29583,29584,29585,29586,29587,29588,29589,29590,29591,29592,29593,29594,29595,29596,29597,29598,29599,29600,29601,29602,29603,29604,29605,29606,29607,29608,29609,29610,29611,29612,29613,29614,29615,29616,29617,29618,29619,29620,29621,29622,29623,29624,29625,29626,29627,29628,29629,29630,29631,29632,29633,29634,29635,29636,29637,29638,29639,29640,29641,29642,29643,29644,29645,29646,29647,29648,29649,29650,29651,29652,29653,29654,29655,29656,29657,29658,29659,29660,29661,29662,29663,29664,29665,29666,29667,29668,29669,29670,29671,29672,29673,29674,29675,29676,29677,29678,29679,29680,29681,29682,29683,29684,29685,29686,29687]

# Only new tracks (>= 29581)
NEW_IDS = [tid for tid in CANDIDATE_IDS if tid >= 29581]


def file_hash(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        sha.update(f.read(1_048_576))
    return sha.hexdigest()[:64]


def parse_stems() -> dict[int, dict]:
    tracks: dict[int, dict] = {}
    for f in sorted(STEMS_DIR.iterdir()):
        if f.is_dir() or f.name.startswith("."):
            continue
        m = PATTERN.match(f.name)
        if not m:
            continue
        idx = int(m.group("index"))
        if idx not in tracks:
            tracks[idx] = {
                "title": m.group("title"),
                "bpm": int(m.group("bpm")),
                "genre": m.group("genre"),
                "stems": {},
            }
        tracks[idx]["stems"][m.group("stem")] = str(f)
    return tracks


async def main():
    all_tracks = parse_stems()

    # Build title -> index mapping
    title_to_idx = {t["title"]: idx for idx, t in all_tracks.items()}

    # Build track_id -> title mapping from DB
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        from app.models.track import Track

        result = await session.execute(
            select(Track.id, Track.title).where(Track.id.in_(NEW_IDS))
        )
        id_to_title = {row.id: row.title for row in result}

    print(f"Found {len(id_to_title)} new tracks with IDs")

    # For each new track, find its instrumental stem and create library item
    async with factory() as session:
        async with UnitOfWork(session) as uow:
            created = 0
            for track_id in sorted(NEW_IDS):
                title = id_to_title.get(track_id)
                if title is None:
                    print(f"  WARN: track {track_id} not found in DB")
                    continue
                
                idx = title_to_idx.get(title)
                if idx is None:
                    print(f"  WARN: no stems for '{title}' (track {track_id})")
                    continue

                t = all_tracks[idx]
                stem_path = t["stems"].get("instrumental")
                if not stem_path:
                    print(f"  WARN: no instrumental stem for '{title}'")
                    continue

                size = os.path.getsize(stem_path)
                item = DjLibraryItem(
                    track_id=track_id,
                    file_path=stem_path,
                    file_hash=file_hash(stem_path),
                    file_size=size,
                    mime_type="audio/mp4",
                    source_app="suno_stems",
                )
                uow.session.add(item)
                await uow.session.flush()

                grid = DjBeatgrid(
                    library_item_id=item.id,
                    bpm=float(t["bpm"]),
                    confidence=0.95,
                    canonical=True,
                    variable_tempo=False,
                )
                uow.session.add(grid)
                created += 1

                if created <= 5 or created % 20 == 0:
                    print(f"  audio #{item.id}: {title} ({t['bpm']} BPM)")

        print(f"\nCreated {created} audio file records with beatgrids")

    print("\nNow ready for feature analysis via MCP:")
    print(f"  entity_create track_features track_ids=[{NEW_IDS[0]},...{NEW_IDS[-1]}]")


if __name__ == "__main__":
    asyncio.run(main())
