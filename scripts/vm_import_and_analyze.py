#!/usr/bin/env python3
"""vm_import_and_analyze.py — continuous importer+analyzer for YM techno library.

Loops over user's YM playlists that look like techno and the Liked tracks,
imports new tracks into the local DB, and runs TieredPipeline up to L5 on
them in batches. Idempotent — re-running is safe.

Usage:
    python scripts/vm_import_and_analyze.py \\
        [--level 5] \\
        [--batch 100] \\
        [--workers 6] \\
        [--test-one] \\
        [--once]

Flags:
    --test-one   Import a single track from "TECHNO FOR DJ SETS" and analyze
                 it to the target level, then exit (smoke test).
    --once       Run one full sweep over all playlists and exit.
    --no-likes   Skip the Liked tracks pool.
    --playlist-filter REGEX
                 Override the default /techno|tech.*house/i regex used to
                 pick which playlists to process.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"vm_import_analyze_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
    ],
)
# Suppress noisy HTTP-per-request logs from yandex client; keep our own progress
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
# Surface analysis pipeline & tiered service progress at INFO
logging.getLogger("app.audio").setLevel(logging.INFO)
logging.getLogger("app.services.tiered_pipeline").setLevel(logging.INFO)

# Force unbuffered stdout so `tail -f` shows live output
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

log = logging.getLogger("loop")

_shutdown = asyncio.Event()


def _on_signal(sig: int, _: Any) -> None:
    log.warning("Signal %s — will stop after current batch", sig)
    _shutdown.set()


signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)


DEFAULT_TECHNO_REGEX = r"techno|tech\s*house|minimal|peak\s*time|dub\s*techno|acid"


async def _fetch_playlist_track_ids(
    ym: Any,
    kind: int,
    owner_id: str,
) -> list[str]:
    """Return YM track IDs for a playlist."""
    try:
        tracks = await ym.get_playlist_tracks(owner_id, kind)
    except Exception as e:
        log.warning("get_playlist_tracks(owner=%s, kind=%s) failed: %s", owner_id, kind, e)
        return []
    return [str(t.id).split(":")[0] for t in tracks if getattr(t, "id", None)]


async def _get_liked_ids(ym: Any) -> list[str]:
    try:
        likes = await ym.get_liked_ids()
        return [str(t).split(":")[0] for t in likes]
    except Exception as e:
        log.warning("get_liked_ids failed: %s", e)
        return []


async def _get_user_playlists(ym: Any) -> list[Any]:
    try:
        return await ym.list_user_playlists()
    except Exception as e:
        log.warning("list_user_playlists failed: %s", e)
        return []


async def _process_refs(
    refs: list[str],
    *,
    batch_size: int,
    target_level: int,
    session_factory: Any,
    registry: Any,
    ym_client: Any,
    workers: int,
    force: bool,
) -> dict[str, int]:
    """Import refs (idempotent) and analyze up to target_level in chunks."""
    from app.audio.level_config import AnalysisLevel
    from app.audio.pipeline import AnalysisPipeline
    from app.repositories.audio import AudioRepository
    from app.repositories.ingestion import IngestionRepository
    from app.repositories.track import TrackRepository
    from app.services.import_service import ImportService
    from app.services.tiered_pipeline import TieredPipeline

    totals = {"imported": 0, "skipped": 0, "analyzed": 0, "failed": 0}
    level = AnalysisLevel(target_level)

    for i in range(0, len(refs), batch_size):
        if _shutdown.is_set():
            break
        chunk = refs[i : i + batch_size]
        log.info(
            "  chunk %d/%d (%d refs)",
            i // batch_size + 1,
            (len(refs) + batch_size - 1) // batch_size,
            len(chunk),
        )
        t0 = time.time()

        async with session_factory() as session:
            track_repo = TrackRepository(session)
            ingestion_repo = IngestionRepository(session)
            audio_repo = AudioRepository(session)
            import_svc = ImportService(
                track_repo=track_repo,
                ym=ym_client,
                ingestion_repo=ingestion_repo,
            )
            result = await import_svc.import_tracks(track_refs=chunk)
            await session.commit()

        totals["imported"] += result.get("imported", 0)
        totals["skipped"] += result.get("skipped", 0)

        local_ids = list((result.get("id_mapping") or {}).values())
        if not local_ids:
            continue

        async with session_factory() as session:
            audio_repo = AudioRepository(session)
            track_repo = TrackRepository(session)
            pipeline = AnalysisPipeline(
                registry=registry,
                use_processes=False,  # ProcessPool deadlocks after BrokenProcessPool
                max_workers=workers,
            )
            tiered = TieredPipeline(
                audio_repo=audio_repo,
                track_repo=track_repo,
                pipeline=pipeline,
                ym_client=ym_client,
                timeseries=None,
            )

            # Wrap _download_and_analyze with live per-track progress logging
            _orig = tiered._download_and_analyze
            counters = {"done": 0, "ok": 0, "fail": 0}
            chunk_total = len(local_ids)
            log_lock = asyncio.Lock()

            async def _wrapped(track_id: int, ym_track_id: str, level_arg: Any) -> Any:
                t_start = time.time()
                try:
                    res = await _orig(track_id, ym_track_id, level_arg)
                    return res
                finally:
                    async with log_lock:
                        counters["done"] += 1
                        ok = res is not None  # type: ignore[has-type]
                        if ok:
                            counters["ok"] += 1
                        else:
                            counters["fail"] += 1
                        log.info(
                            "    [%d/%d] track=%d ym=%s %s in %.1fs (ok=%d fail=%d)",
                            counters["done"],
                            chunk_total,
                            track_id,
                            ym_track_id,
                            "OK" if ok else "FAIL",
                            time.time() - t_start,
                            counters["ok"],
                            counters["fail"],
                        )

            tiered._download_and_analyze = _wrapped  # type: ignore[method-assign]

            try:
                res = await tiered.ensure_level(local_ids, level, force=force)
                await session.commit()
            except Exception as e:
                await session.rollback()
                log.error("  TieredPipeline error: %s", e, exc_info=True)
                res = {"analyzed": 0, "failed": len(local_ids), "skipped": 0}

        totals["analyzed"] += res.get("analyzed", 0)
        totals["failed"] += res.get("failed", 0)

        elapsed = time.time() - t0
        rate = len(local_ids) / elapsed if elapsed > 0 else 0
        log.info(
            "  chunk done in %.1fs (%.1f tr/s) imp=%d skip=%d ana=%d fail=%d",
            elapsed,
            rate,
            result.get("imported", 0),
            result.get("skipped", 0),
            res.get("analyzed", 0),
            res.get("failed", 0),
        )

    return totals


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=5, choices=[2, 3, 4, 5])
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--workers", type=int, default=0, help="0=auto")
    ap.add_argument("--test-one", action="store_true")
    ap.add_argument(
        "--test-batch",
        type=int,
        default=0,
        help="Take first N refs from TECHNO FOR DJ SETS, process one batch, exit",
    )
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--no-likes", action="store_true")
    ap.add_argument(
        "--playlist-filter",
        default=DEFAULT_TECHNO_REGEX,
        help="Regex to select YM playlists by title",
    )
    ap.add_argument("--sleep", type=int, default=600, help="Seconds between loops")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cpu = os.cpu_count() or 4
    if args.workers == 0:
        args.workers = max(2, min(cpu // 2, 8))

    os.environ.setdefault("DJ_AUDIO_SCORING_WORKERS", str(args.workers))
    os.environ.setdefault("DJ_AUDIO_TRIAGE_WORKERS", str(min(args.workers + 2, cpu)))

    # Pre-compile numba JIT functions on the main thread BEFORE the pipeline
    # spins up its ThreadPoolExecutor. Without this, multiple threads call
    # librosa.beat.beat_track / chroma_cqt / onset_strength simultaneously and
    # numba's first-time JIT compilation races inside C → SIGSEGV.
    log.info("warming up numba/librosa JIT (one-time, ~10–30s)...")
    _t0 = time.time()
    try:
        import librosa  # type: ignore
        import numpy as np  # type: ignore

        _sr = 22050
        _dummy = np.random.RandomState(42).randn(_sr * 5).astype(np.float32) * 0.1
        librosa.onset.onset_strength(y=_dummy, sr=_sr)
        librosa.beat.beat_track(y=_dummy, sr=_sr)
        librosa.feature.chroma_cqt(y=_dummy, sr=_sr)
        librosa.feature.mfcc(y=_dummy, sr=_sr, n_mfcc=13)
        librosa.feature.spectral_centroid(y=_dummy, sr=_sr)
        log.info("JIT warmup done in %.1fs", time.time() - _t0)
    except Exception as e:
        log.warning("JIT warmup skipped: %s", e)

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.audio.analyzers.base import AnalyzerRegistry
    from app.config import settings
    from app.ym.client import YandexMusicClient
    from app.ym.rate_limiter import RateLimiter

    log.info("=" * 70)
    log.info("DJ Music Plugin — YM Importer + Analyzer")
    log.info(
        "level=L%d batch=%d workers=%d cpu=%d test_one=%s once=%s",
        args.level,
        args.batch,
        args.workers,
        cpu,
        args.test_one,
        args.once,
    )
    log.info("DB: %s...", settings.database_url[:55])
    log.info("=" * 70)

    connect_args: dict[str, Any] = {}
    if settings.database_url.startswith("postgresql"):
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, connect_args=connect_args
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    registry = AnalyzerRegistry()
    registry.discover()
    log.info("analyzers: %s", ", ".join(sorted(registry.list_available())))

    ym_client = YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=RateLimiter(
            delay=settings.ym_rate_limit_delay,
            max_retries=settings.ym_retry_attempts,
        ),
    )

    try:
        if args.test_one or args.test_batch > 0:
            n = 1 if args.test_one else args.test_batch
            log.info(
                "[TEST] importing %d tracks from TECHNO FOR DJ SETS (kind=1280)",
                n,
            )
            refs = await _fetch_playlist_track_ids(ym_client, 1280, settings.ym_user_id)
            if not refs:
                log.error("No tracks found in playlist 1280")
                return
            picked = refs[:n]
            log.info("[TEST] picked %d / %d total in playlist", len(picked), len(refs))
            stats = await _process_refs(
                picked,
                batch_size=args.batch,
                target_level=args.level,
                session_factory=session_factory,
                registry=registry,
                ym_client=ym_client,
                workers=args.workers,
                force=args.force,
            )
            log.info("[TEST] done: %s", stats)
            return

        pattern = re.compile(args.playlist_filter, re.IGNORECASE)

        loop_num = 0
        while not _shutdown.is_set():
            loop_num += 1
            log.info("═" * 70)
            log.info("LOOP #%d", loop_num)
            log.info("═" * 70)

            loop_totals = {"imported": 0, "skipped": 0, "analyzed": 0, "failed": 0}

            if not args.no_likes:
                log.info("[pool] Liked tracks")
                liked = await _get_liked_ids(ym_client)
                log.info("  %d liked ids", len(liked))
                if liked and not _shutdown.is_set():
                    stats = await _process_refs(
                        liked,
                        batch_size=args.batch,
                        target_level=args.level,
                        session_factory=session_factory,
                        registry=registry,
                        ym_client=ym_client,
                        workers=args.workers,
                        force=args.force,
                    )
                    for k, v in stats.items():
                        loop_totals[k] = loop_totals.get(k, 0) + v

            playlists = await _get_user_playlists(ym_client)
            techno_pls = [
                p
                for p in playlists
                if getattr(p, "title", None)
                and pattern.search(str(p.title))
                and int(getattr(p, "track_count", 0) or 0) > 0
            ]
            log.info(
                "[pool] %d/%d playlists match filter /%s/",
                len(techno_pls),
                len(playlists),
                args.playlist_filter,
            )

            for pl in techno_pls:
                if _shutdown.is_set():
                    break
                kind = int(pl.kind)
                title = pl.title
                owner = str(getattr(pl, "owner_id", None) or settings.ym_user_id)
                log.info(
                    "[pool] %s (kind=%s, owner=%s, tracks=%s)",
                    title,
                    kind,
                    owner,
                    pl.track_count,
                )
                refs = await _fetch_playlist_track_ids(ym_client, kind, owner)
                log.info("  %d track ids", len(refs))
                if not refs:
                    continue
                stats = await _process_refs(
                    refs,
                    batch_size=args.batch,
                    target_level=args.level,
                    session_factory=session_factory,
                    registry=registry,
                    ym_client=ym_client,
                    workers=args.workers,
                    force=args.force,
                )
                for k, v in stats.items():
                    loop_totals[k] = loop_totals.get(k, 0) + v

            log.info("LOOP #%d totals: %s", loop_num, loop_totals)

            if args.once or _shutdown.is_set():
                break

            log.info("sleeping %ds before next loop...", args.sleep)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(_shutdown.wait(), timeout=args.sleep)
    finally:
        await ym_client.close()
        await engine.dispose()
        log.info("shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
