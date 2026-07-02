#!/usr/bin/env python3
"""Continuous Beatport genre backfill over the whole library — VM batch job.

For every track without a Beatport verdict yet, match it on Beatport
(title+artist, BPM/duration-verified via the real provider adapter) and persist
the human-curated genre into the ``beatport_*`` columns of
``track_audio_features_computed``.

Resumable + idempotent. New tracks are searched once. Rows matched by the old
genre-only backfill are refreshed directly by ``beatport_track_id`` (no search)
until the complete metadata payload has been persisted.

Network-bound (Beatport rate-limited), so it co-exists with the CPU-bound L5
sweep without contention. Verified metadata becomes canonical while original
audio values remain in ``audio_*`` columns. The L5 writer is source-aware and
therefore cannot clobber Beatport-authoritative values.

Run on the VM:
    PYTHONUNBUFFERED=1 uv run python -u scripts/vm_beatport_backfill.py \
        --workers 6 2>&1 | tee -a /var/log/dj_beatport.log

Flags:
    --workers N   concurrent match tasks (default 6; Beatport rate-limiter caps
                  actual throughput regardless)
    --batch N     DB page size when pulling pending track ids (default 500)
    --limit N     stop after N tracks (default: all)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
import time
from typing import Any

from sqlalchemy import select

from app.db.session import dispose, get_session_factory
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed as TF  # noqa: N814
from app.providers.beatport.canonical import canonical_mood_result, canonical_updates
from app.repositories.unit_of_work import UnitOfWork
from app.server.lifespan import build_beatport_adapter

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("bp")


def _split_artist_title(title: str | None) -> tuple[str, str]:
    raw = (title or "").strip()
    if " - " in raw:
        artist, _, t = raw.partition(" - ")
        return artist.strip(), t.strip()
    return "", raw


async def _canonicalize_stored_genres(session_factory: Any) -> int:
    """Apply already-stored high-confidence genres without any API calls."""
    async with session_factory() as session:
        rows = list(
            (
                await session.execute(
                    select(TF).where(
                        TF.beatport_confidence == "high",
                        TF.beatport_genre.is_not(None),
                        (TF.mood_source.is_(None)) | (TF.mood_source != "beatport"),
                    )
                )
            )
            .scalars()
            .all()
        )
        changed = 0
        for row in rows:
            mood = canonical_mood_result(
                genre=row.beatport_genre,
                sub_genre=row.beatport_sub_genre,
                bpm=row.bpm,
                energy_mean=row.energy_mean,
                audio_mood=row.mood,
            )
            if mood is None:
                continue
            row.audio_bpm = row.audio_bpm if row.audio_bpm is not None else row.bpm
            row.audio_bpm_confidence = (
                row.audio_bpm_confidence
                if row.audio_bpm_confidence is not None
                else row.bpm_confidence
            )
            row.audio_key_code = (
                row.audio_key_code if row.audio_key_code is not None else row.key_code
            )
            row.audio_key_confidence = (
                row.audio_key_confidence
                if row.audio_key_confidence is not None
                else row.key_confidence
            )
            row.audio_mood = row.audio_mood if row.audio_mood is not None else row.mood
            row.audio_mood_confidence = (
                row.audio_mood_confidence
                if row.audio_mood_confidence is not None
                else row.mood_confidence
            )
            row.mood = mood.value
            row.mood_confidence = mood.confidence
            row.mood_source = "beatport"
            changed += 1
        await session.commit()
        return changed


async def _pending(
    session_factory: Any, limit: int | None
) -> list[tuple[int, str | None, float | None, int | None, int | None, str | None]]:
    async with session_factory() as session:
        stmt = (
            select(
                TF.track_id,
                Track.title,
                TF.bpm,
                Track.duration_ms,
                TF.beatport_track_id,
                TF.beatport_confidence,
            )
            .join(Track, Track.id == TF.track_id)
            .where(
                TF.beatport_confidence.is_(None)
                | (TF.beatport_confidence.in_(("high", "medium")) & TF.beatport_bpm.is_(None))
            )
            .order_by(TF.track_id)
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).all()
    return [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]


async def _process_one(
    row: tuple[int, str | None, float | None, int | None, int | None, str | None],
    adapter: Any,
    session_factory: Any,
    counters: dict[str, int],
    total: int,
    lock: asyncio.Lock,
) -> None:
    track_id, title, bpm, duration_ms, known_beatport_id, known_confidence = row
    t0 = time.time()
    status = "FAIL"
    note = ""
    try:
        if known_beatport_id is not None and known_confidence in ("high", "medium"):
            metadata = await adapter.read("track", str(known_beatport_id), {})
            verdict = {
                **metadata,
                "matched": True,
                "confidence": known_confidence,
                "track": metadata,
            }
        else:
            artist, ttl = _split_artist_title(title)
            if not artist and ttl:
                async with session_factory() as s:
                    artist = await UnitOfWork(s).tracks.get_primary_artist_name(track_id) or ""
            if not ttl:
                verdict = {"matched": False, "confidence": "none"}
            else:
                params: dict[str, Any] = {"artist": artist, "title": ttl}
                if bpm is not None:
                    params["bpm"] = float(bpm)
                if duration_ms is not None:
                    params["duration_ms"] = int(duration_ms)
                verdict = await adapter.read("track_match", None, params)

        async with session_factory() as session:
            uow = UnitOfWork(session)
            if verdict.get("matched"):
                current = await uow.track_features.get_by_track_id(track_id)
                await uow.track_features.upsert(
                    track_id=track_id,
                    **canonical_updates(verdict, current=current),
                )
                if verdict.get("confidence") == "high" and verdict.get("length_ms") is not None:
                    track = await uow.tracks.get(track_id)
                    if track is not None:
                        track.duration_ms = int(verdict["length_ms"])
                status = "MATCH"
                note = f"{verdict.get('confidence')} {verdict.get('genre')}"
            else:
                # Sentinel so a restart never re-searches this track.
                await uow.track_features.upsert(track_id=track_id, beatport_confidence="none")
                status = "NONE"
                note = f"no match ({verdict.get('confidence')})"
            await session.commit()
    except Exception as e:  # one bad track must not kill the backfill
        note = f"ERROR {type(e).__name__}: {e}"[:160]
    finally:
        async with lock:
            counters["done"] += 1
            if status == "MATCH":
                counters["match"] += 1
            elif status == "NONE":
                counters["none"] += 1
            else:
                counters["fail"] += 1
            log.info(
                "[%d/%d] track=%s %s in %.1fs (match=%d none=%d fail=%d) %s",
                counters["done"],
                total,
                track_id,
                status,
                time.time() - t0,
                counters["match"],
                counters["none"],
                counters["fail"],
                note,
            )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--batch", type=int, default=500)  # reserved; full pull today
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    adapter = build_beatport_adapter()
    if adapter is None:
        log.error("Beatport adapter unavailable — set DJ_BEATPORT_USERNAME/PASSWORD in .env")
        return

    session_factory = get_session_factory()
    canonicalized = await _canonicalize_stored_genres(session_factory)
    log.info("canonicalized %d stored Beatport genres without network", canonicalized)
    pending = await _pending(session_factory, args.limit or None)
    total = len(pending)
    log.info("pending Beatport backfill: %d tracks, %d workers", total, args.workers)
    if not total:
        log.info("nothing to do — every track already has a beatport verdict")
        await adapter.close()
        await dispose()
        return

    counters = {"done": 0, "match": 0, "none": 0, "fail": 0}
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(args.workers)

    async def _guarded(
        row: tuple[int, str | None, float | None, int | None, int | None, str | None],
    ) -> None:
        async with sem:
            await _process_one(row, adapter, session_factory, counters, total, lock)

    t0 = time.time()
    try:
        await asyncio.gather(*(_guarded(r) for r in pending))
    finally:
        await adapter.close()
    dt = time.time() - t0
    log.info(
        "DONE: %d match, %d none, %d fail in %.0fs (%.2fs/track avg)",
        counters["match"],
        counters["none"],
        counters["fail"],
        dt,
        dt / max(1, total),
    )
    await dispose()


if __name__ == "__main__":
    asyncio.run(main())
