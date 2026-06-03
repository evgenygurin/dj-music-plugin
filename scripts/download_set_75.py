"""Download audio files for set version 75 (FILTER_SWEEP Hypnotic Roller).

Usage:
    uv run python scripts/download_set_75.py

Downloads 8 tracks via Yandex Music to cache/audio/ and inserts rows
into dj_library_items via the existing audio_file_download handler.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("dl_set75")

# ── Set tracks ─────────────────────────────────────────────────────
TRACKS = [
    {
        "pos": 1,
        "track_id": 18490,
        "ym_id": "53148073",
        "title": "Audiomolekul - Hansekoggen",
        "bpm": 126.0,
        "camelot": "8B",
    },
    {
        "pos": 2,
        "track_id": 9086,
        "ym_id": "79434438",
        "title": "Koer - Apocalypse",
        "bpm": 127.5,
        "camelot": "9A",
    },
    {
        "pos": 3,
        "track_id": 5222,
        "ym_id": "147877085",
        "title": "Sam Paganini - Hypnotize",
        "bpm": 128.4,
        "camelot": "5A",
    },
    {
        "pos": 4,
        "track_id": 12050,
        "ym_id": "23994852",
        "title": "Mixael P - Youre Not Ugly",
        "bpm": 128.4,
        "camelot": "4A",
    },
    {
        "pos": 5,
        "track_id": 12042,
        "ym_id": "4226593",
        "title": "Minimal Collective - Stick/Swab",
        "bpm": 128.4,
        "camelot": "4B",
    },
    {
        "pos": 6,
        "track_id": 11430,
        "ym_id": "81835495",
        "title": "Sascha Audit - Clinical",
        "bpm": 131.7,
        "camelot": "10B",
    },
    {
        "pos": 7,
        "track_id": 10479,
        "ym_id": "112319784",
        "title": "Gvido Binelli - Eremita 44",
        "bpm": 129.9,
        "camelot": "8B",
    },
    {
        "pos": 8,
        "track_id": 19569,
        "ym_id": "39588675",
        "title": "Boozebus - Wasser",
        "bpm": 127.6,
        "camelot": "4B",
    },
]


async def main() -> None:
    # Load settings (reads .env automatically)
    from app.config import get_settings
    from app.db.session import get_session_factory
    from app.providers.yandex.client import YandexClient

    settings = get_settings()
    token = settings.yandex.token
    user_id = str(settings.yandex.user_id)

    if not token:
        log.error("DJ_YM_TOKEN not set — cannot download")
        sys.exit(1)

    audio_dir = Path("cache/audio")
    audio_dir.mkdir(parents=True, exist_ok=True)

    log.info("Starting download of %d tracks for set version 75", len(TRACKS))

    ok = 0
    fail = 0
    skipped = 0

    import hashlib

    client = YandexClient(token=token, user_id=user_id)
    results: list[dict] = []
    try:
        for i, track in enumerate(TRACKS):
            dest = audio_dir / f"track_{track['track_id']}_{track['ym_id']}.mp3"

            if dest.exists():
                log.info(
                    "[%d/%d] SKIP  %s — file already on disk",
                    i + 1,
                    len(TRACKS),
                    track["title"],
                )
                skipped += 1
                results.append({"track_id": track["track_id"], "path": str(dest), "skipped": True})
                continue

            t0 = time.time()
            try:
                downloaded_path = await client.download_track(
                    track_id=track["ym_id"],
                    dest=dest,
                )
                elapsed = time.time() - t0

                file_bytes = Path(downloaded_path).read_bytes()
                sha256 = hashlib.sha256(file_bytes).hexdigest()
                size = len(file_bytes)

                ok += 1
                log.info(
                    "[%d/%d] OK    %s — %.1f MB in %.1fs  sha256=%s",
                    i + 1,
                    len(TRACKS),
                    track["title"],
                    size / 1_048_576,
                    elapsed,
                    sha256[:12],
                )
                results.append(
                    {
                        "track_id": track["track_id"],
                        "path": str(downloaded_path),
                        "sha256": sha256,
                        "size": size,
                        "skipped": False,
                    }
                )
            except Exception as exc:
                fail += 1
                elapsed = time.time() - t0
                log.error(
                    "[%d/%d] FAIL  %s — %s (%.1fs)",
                    i + 1,
                    len(TRACKS),
                    track["title"],
                    exc,
                    elapsed,
                )

            # Rate-limit gap
            if i < len(TRACKS) - 1:
                await asyncio.sleep(2.0)
    finally:
        await client.close()

    # Print SQL for manual Supabase insert
    log.info("Done: ok=%d  fail=%d  skipped=%d", ok, fail, skipped)
    if results:
        log.info("--- INSERT SQL ---")
        rows = []
        for r in results:
            if not r.get("skipped"):
                rows.append(
                    f"({r['track_id']}, '{r['path']}', 'file://{r['path']}', "
                    f"'{r['sha256']}', {r['size']}, 'audio/mpeg', 'download_set_75')"
                )
        if rows:
            sql = (
                "INSERT INTO dj_library_items (track_id, file_path, file_uri, file_hash, file_size, mime_type, source_app) VALUES\n"
                + ",\n".join(rows)
                + "\nON CONFLICT (track_id) DO NOTHING;"
            )
            print(sql)

    log.info("Done: ok=%d  fail=%d  skipped=%d", ok, fail, skipped)


if __name__ == "__main__":
    asyncio.run(main())
