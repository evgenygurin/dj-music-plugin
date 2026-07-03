#!/usr/bin/env python3
"""Build the DJ USB: download every track in the manifest into its crate folder.

Reads /tmp/usb_manifest.csv (crate, rank, track_id, yandex_id, camelot, bpm,
energy, lufs, q, title) and downloads each MP3 from Yandex into
<USB_ROOT>/<crate>/<rank> [<camelot>] [<bpm>] <title>.mp3.

Resumable (skips files already on disk), concurrent (semaphore), per-track
progress logging. Run locally (YM HTTP works on the laptop; the asyncpg DB
does not, hence the manifest is pre-baked on the VM).
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

USB_ROOT = Path.home() / "DJ_USB_BUILD"
MANIFEST = Path("/tmp/usb_manifest.csv")
WORKERS = 4

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
for n in ("httpx", "httpcore"):
    logging.getLogger(n).setLevel(logging.WARNING)
log = logging.getLogger("usb")


def fname(rank: str, cam: str, bpm: str, title: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9 ()&_.,-]", "", title).strip()[:80]
    cam = cam or "--"
    return f"{int(rank):04d} [{cam}] [{bpm}] {safe}.mp3"


def load() -> list[dict]:
    with MANIFEST.open() as fh:
        return list(csv.DictReader(fh))


async def main() -> None:
    rows = load()
    total = len(rows)
    log.info("USB build: %d tracks -> %s", total, USB_ROOT)
    s = get_settings()
    client = YandexClient(
        token=s.yandex.token,
        user_id=str(s.yandex.user_id),
        base_url=s.yandex.base_url,
        rate_limiter=TokenBucketRateLimiter(delay_s=1.0),
    )
    counters = {"done": 0, "ok": 0, "skip": 0, "fail": 0}
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(WORKERS)

    async def one(r: dict) -> None:
        crate_dir = USB_ROOT / r["crate"]
        dest = crate_dir / fname(r["rank"], r["camelot"], r["bpm"], r["title"])
        t0 = time.time()
        status = "FAIL"
        try:
            if dest.exists() and dest.stat().st_size > 500_000:
                status = "SKIP"
            else:
                crate_dir.mkdir(parents=True, exist_ok=True)
                async with sem:
                    await client.download_track(r["yandex_id"], dest)
                status = "OK"
        except Exception as e:  # one bad track must not kill the build
            status = "FAIL"
            note = f"{type(e).__name__}: {e}"[:120]
        else:
            note = dest.name[:50]
        async with lock:
            counters["done"] += 1
            counters[{"OK": "ok", "SKIP": "skip", "FAIL": "fail"}[status]] += 1
            log.info(
                "[%d/%d] %s %-5s in %.1fs (ok=%d skip=%d fail=%d) %s",
                counters["done"],
                total,
                r["crate"],
                status,
                time.time() - t0,
                counters["ok"],
                counters["skip"],
                counters["fail"],
                note,
            )

    try:
        await asyncio.gather(*(one(r) for r in rows))
    finally:
        await client.close()
    log.info(
        "DONE: ok=%d skip=%d fail=%d / %d",
        counters["ok"],
        counters["skip"],
        counters["fail"],
        total,
    )


if __name__ == "__main__":
    asyncio.run(main())
