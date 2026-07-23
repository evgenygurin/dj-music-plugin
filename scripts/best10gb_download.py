#!/usr/bin/env python3
"""Download the best-quality techno tracks (manifest CSV) into DEST_DIR,
stopping as soon as the cumulative downloaded size hits TARGET_BYTES.

Manifest: /tmp/best10gb_manifest.csv (rank,track_id,yandex_id,title,bpm,mood,
key_code,duration_ms,quality) — pre-ranked best-first by a feature-first
quality score (energy_mean + kick_prominence + bpm-centrality + hp_ratio +
techno-mood bonus).

Sequential by rank (best tracks first), single-flight (YM rate limit),
resumable (skips files already on disk), stops exactly at the byte cap so
we don't blow past 10 GB.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import logging
import re
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.providers.yandex.client import YandexClient
from app.providers.yandex.rate_limiter import TokenBucketRateLimiter

DEST_DIR = Path.home() / "DJ_Best_10GB"
MANIFEST = Path("/tmp/best10gb_manifest2.csv")
TARGET_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
for n in ("httpx", "httpcore"):
    logging.getLogger(n).setLevel(logging.WARNING)
log = logging.getLogger("best10gb")


def fname(rank: str, bpm: str, mood: str, title: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9 ()&_.,-]", "", title).strip()[:80]
    try:
        bpm_i = f"{float(bpm):.0f}"
    except ValueError:
        bpm_i = bpm
    return f"{int(rank):04d} [{bpm_i}bpm] [{mood}] {safe}.mp3"


def load() -> list[dict]:
    with MANIFEST.open() as fh:
        return list(csv.DictReader(fh))


async def main() -> None:
    rows = load()
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    s = get_settings()
    client = YandexClient(
        token=s.yandex.token,
        user_id=str(s.yandex.user_id),
        base_url=s.yandex.base_url,
        rate_limiter=TokenBucketRateLimiter(delay_s=1.2),
    )

    # Seed cumulative size from anything already on disk (resume support).
    cum_bytes = sum(p.stat().st_size for p in DEST_DIR.glob("*.mp3"))
    counters = {"done": 0, "ok": 0, "skip": 0, "fail": 0}
    log.info(
        "best10gb: %d candidates -> %s (already have %.2f GB)",
        len(rows),
        DEST_DIR,
        cum_bytes / 1024**3,
    )

    for r in rows:
        if cum_bytes >= TARGET_BYTES:
            log.info("TARGET REACHED: %.2f GB >= 10 GB — stopping", cum_bytes / 1024**3)
            break
        dest = DEST_DIR / fname(r["rank"], r["bpm"], r["mood"], r["title"])
        t0 = time.time()
        note = ""
        if dest.exists() and dest.stat().st_size > 500_000:
            status = "SKIP"
        else:
            try:
                await client.download_track(r["yandex_id"], dest)
                status = "OK"
                cum_bytes += dest.stat().st_size
            except Exception as e:  # one bad track must not kill the run
                status = "FAIL"
                note = f"{type(e).__name__}: {e}"[:120]
        counters["done"] += 1
        counters[{"OK": "ok", "SKIP": "skip", "FAIL": "fail"}[status]] += 1
        log.info(
            "[%d/%d] rank=%s %-5s in %.1fs cum=%.2fGB (ok=%d skip=%d fail=%d) %s",
            counters["done"],
            len(rows),
            r["rank"],
            status,
            time.time() - t0,
            cum_bytes / 1024**3,
            counters["ok"],
            counters["skip"],
            counters["fail"],
            note or dest.name[:50],
        )

    await client.close()
    log.info(
        "DONE: ok=%d skip=%d fail=%d total=%.2fGB dest=%s",
        counters["ok"],
        counters["skip"],
        counters["fail"],
        cum_bytes / 1024**3,
        DEST_DIR,
    )


if __name__ == "__main__":
    asyncio.run(main())
