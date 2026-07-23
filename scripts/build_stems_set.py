"""Step 1: Parse stems, check existing, create new tracks + audio files.

Run: uv run python scripts/build_stems_set.py
"""
import asyncio
import hashlib
import os
import re
import sys
from pathlib import Path

from fastmcp import Client
from app.db.session import get_session_factory
from app.models.audio_file import DjBeatgrid, DjLibraryItem
from app.repositories.unit_of_work import UnitOfWork
from app.server.app import build_mcp_server

STEMS_DIR = Path("/Users/laptop/Desktop/Stems")
PATTERN = re.compile(
    r"^(?P<index>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>\w+)\]\s+(?P<title>.+?)-(?P<stem>\w+)\.m4a$"
)


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
    print("=== Step 1: Parse stems ===")
    all_tracks = parse_stems()
    print(f"Total unique stems tracks: {len(all_tracks)}")

    target_genres = {"acid", "peak_time"}
    bpm_min, bpm_max = 126, 133

    candidates = {
        idx: t for idx, t in all_tracks.items()
        if t["genre"] in target_genres and bpm_min <= t["bpm"] <= bpm_max
    }
    print(f"Candidates (acid/peak_time, {bpm_min}-{bpm_max} BPM): {len(candidates)}")

    # Check existing tracks
    print("\n=== Step 2: Check existing tracks ===")
    mcp = build_mcp_server()
    async with Client(mcp) as client:
        r = await client.call_tool("entity_list", {
            "entity": "track", "limit": 500, "with_total": True,
        })
        data = r.structured_content
        existing = {t.get("title", "").lower(): t["id"] for t in data.get("items", [])}
        print(f"Existing tracks in library: {len(existing)}")

    new_tracks = {
        idx: t for idx, t in candidates.items()
        if t["title"].lower() not in existing
    }
    print(f"New tracks to create: {len(new_tracks)}")

    # Map track IDs
    id_map: dict[int, int] = {}
    for idx, t in candidates.items():
        if t["title"].lower() in existing:
            id_map[idx] = existing[t["title"].lower()]

    if new_tracks:
        print(f"\n=== Step 3: Creating {len(new_tracks)} new tracks ===")
        factory = get_session_factory()
        async with factory() as session:
            async with UnitOfWork(session) as uow:
                for idx in sorted(new_tracks.keys()):
                    t = new_tracks[idx]
                    row = await uow.tracks.create(
                        title=t["title"],
                        sort_title=t["title"].lower(),
                        duration_ms=None,
                    )
                    id_map[idx] = row.id
                    if (len(id_map) - len(existing)) <= 5 or len(id_map) % 20 == 0:
                        print(f"  track #{row.id}: {t['title']} ({t['bpm']} BPM, {t['genre']})")
        print(f"Created {len(new_tracks)} tracks")

    else:
        print("All candidates already exist in library")

    candidate_ids = sorted(id_map[idx] for idx in candidates if idx in id_map)
    print(f"\nTotal candidate track_ids: {len(candidate_ids)}")

    # Write IDs to file for next steps
    with open("/tmp/stems_candidate_ids.txt", "w") as f:
        f.write(",".join(str(x) for x in candidate_ids))

    # Print for copy-paste
    print(f"\nTrack IDs ({len(candidate_ids)} total):")
    print(",".join(str(x) for x in candidate_ids))


if __name__ == "__main__":
    asyncio.run(main())
