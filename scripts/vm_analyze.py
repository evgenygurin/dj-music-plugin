#!/usr/bin/env python3
"""
vm_analyze.py — массовый анализ треков на удалённой VM.

Использование:
    python scripts/vm_analyze.py [--level 5] [--batch 200] [--workers 20] [--force]

Уровни анализа:
    2 (TRIAGE)     — BPM, LUFS, энергия, спектр, key, MFCC
    3 (SCORING)    — + beat (onset, kick, hp_ratio, pulse)
    4 (TRANSITION) — + structure (секции)
    5 (ADVANCED)   — + L5: danceability, dissonance, tonnetz, tempogram, ...

Для VM 60 cores / 32 GB RAM рекомендуется:
    --workers 20 --level 5
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import time
from datetime import datetime
from typing import Any

# ── Setup logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"vm_analyze_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Graceful shutdown ────────────────────────────────────────────────────────
_shutdown = asyncio.Event()


def _on_signal(sig: int, _: Any) -> None:
    log.warning("Signal %s received — finishing current batch and stopping...", sig)
    _shutdown.set()


signal.signal(signal.SIGINT, _on_signal)
signal.signal(signal.SIGTERM, _on_signal)


# ── Main ─────────────────────────────────────────────────────────────────────
async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch track analysis for DJ Music Plugin")
    parser.add_argument(
        "--level",
        type=int,
        default=5,
        choices=[2, 3, 4, 5],
        help="Target analysis level (default: 5 = ADVANCED)",
    )
    parser.add_argument(
        "--batch", type=int, default=200, help="Tracks per processing batch (default: 200)"
    )
    parser.add_argument(
        "--workers", type=int, default=0, help="Parallel workers (0 = auto based on CPU cores)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Re-analyze tracks already at target level"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show how many tracks need analysis without running"
    )
    parser.add_argument(
        "--offset", type=int, default=0, help="Skip first N tracks (resume from checkpoint)"
    )
    args = parser.parse_args()

    # ── Auto workers ─────────────────────────────────────────────────────────
    cpu_cores = os.cpu_count() or 4
    if args.workers == 0:
        if args.level <= 2:
            args.workers = min(cpu_cores - 4, 24)
        elif args.level == 3:
            args.workers = min(cpu_cores - 4, 20)
        else:
            args.workers = min(cpu_cores // 3, 16)
        args.workers = max(args.workers, 2)

    log.info("=" * 60)
    log.info("DJ Music Plugin — VM Batch Analyzer")
    log.info(
        "Level: %s | Workers: %d | Batch: %d | Force: %s",
        _level_name(args.level),
        args.workers,
        args.batch,
        args.force,
    )
    log.info("CPU cores detected: %d", cpu_cores)
    log.info("=" * 60)

    # ── Apply env overrides for worker counts ─────────────────────────────────
    _apply_worker_env(args.workers, args.level)

    # ── Import app modules after env is set ───────────────────────────────────
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from dj_music.audio.analyzers.base import AnalyzerRegistry
    from dj_music.audio.level_config import AnalysisLevel
    from dj_music.audio.pipeline import AnalysisPipeline
    from dj_music.core.config import settings
    from dj_music.repositories.audio import AudioRepository
    from dj_music.repositories.track import TrackRepository
    from dj_music.services.tiered_pipeline import TieredPipeline
    from dj_music.ym.client import YandexMusicClient
    from dj_music.ym.rate_limiter import RateLimiter

    target = AnalysisLevel(args.level)

    log.info("DB: %s", settings.database_url[:60] + "...")
    log.info("YM user: %s | Rate limit: %.1fs", settings.ym_user_id, settings.ym_rate_limit_delay)

    # ── Build DB session factory ──────────────────────────────────────────────
    connect_args: dict[str, Any] = {}
    if settings.database_url.startswith("postgresql"):
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=60,  # Supabase drops idle connections after ~5 min
        pool_size=3,
        max_overflow=2,
        connect_args=connect_args,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # ── Build analyzer registry ───────────────────────────────────────────────
    registry = AnalyzerRegistry()
    registry.discover()
    available = registry.list_available()
    log.info("Available analyzers (%d): %s", len(available), ", ".join(available))

    # ── Get tracks needing analysis ───────────────────────────────────────────
    async with session_factory() as session:
        result = await session.execute(
            text("""
            SELECT t.id
            FROM tracks t
            LEFT JOIN track_audio_features_computed f ON f.track_id = t.id
            WHERE t.status = 0
              AND (f.track_id IS NULL OR f.analysis_level < :target_level)
            ORDER BY t.id
        """),
            {"target_level": int(target)},
        )
        all_ids = [row[0] for row in result.fetchall()]

        total_result = await session.execute(text("SELECT COUNT(*) FROM tracks WHERE status = 0"))
        total_tracks = total_result.scalar()
        already_result = await session.execute(
            text(
                "SELECT COUNT(*) FROM track_audio_features_computed WHERE analysis_level >= :lvl"
            ),
            {"lvl": int(target)},
        )
        already_done = already_result.scalar()

    log.info("Total active tracks: %d", total_tracks)
    log.info("Already at L%d+: %d", args.level, already_done)
    log.info("Need analysis: %d", len(all_ids))

    if args.force:
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT id FROM tracks WHERE status = 0 ORDER BY id")
            )
            all_ids = [row[0] for row in result.fetchall()]
        log.info("Force mode: analyzing all %d tracks", len(all_ids))

    if args.offset > 0:
        all_ids = all_ids[args.offset :]
        log.info("Resuming from offset %d, %d tracks remaining", args.offset, len(all_ids))

    if args.dry_run:
        log.info("DRY RUN — exiting without analysis")
        _print_eta(len(all_ids), args.workers, args.level)
        return

    if not all_ids:
        log.info("Nothing to analyze — all tracks are already at L%d+", args.level)
        return

    _print_eta(len(all_ids), args.workers, args.level)

    # ── Initialize YM client ──────────────────────────────────────────────────
    ym_client = YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=RateLimiter(
            delay=settings.ym_rate_limit_delay,
            max_retries=settings.ym_retry_attempts,
        ),
    )

    # ── Process in batches ────────────────────────────────────────────────────
    total = len(all_ids)
    done = 0
    failed = 0
    start_time = time.time()
    batch_num = 0

    for batch_start in range(0, total, args.batch):
        if _shutdown.is_set():
            log.warning("Shutdown requested — stopping at batch %d", batch_num)
            break

        batch_ids = all_ids[batch_start : batch_start + args.batch]
        batch_num += 1

        log.info(
            "[Batch %d] Processing %d tracks (IDs %d–%d) | Done: %d/%d (%.1f%%)",
            batch_num,
            len(batch_ids),
            batch_ids[0],
            batch_ids[-1],
            done,
            total,
            100 * done / total if total else 0,
        )

        try:
            async with session_factory() as session:
                audio_repo = AudioRepository(session)
                track_repo = TrackRepository(session)
                pipeline = AnalysisPipeline(
                    registry=registry,
                    use_processes=False,
                    max_workers=args.workers,
                )
                tiered = TieredPipeline(
                    audio_repo=audio_repo,
                    track_repo=track_repo,
                    pipeline=pipeline,
                    ym_client=ym_client,
                    timeseries=None,
                )
                result = await tiered.ensure_level(
                    batch_ids,
                    target,
                    force=args.force,
                )
                await session.commit()

            batch_analyzed = result.get("analyzed", 0)
            batch_skipped = result.get("skipped", 0)
            batch_failed = result.get("failed", 0)

            done += batch_analyzed + batch_skipped
            failed += batch_failed

            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (total - done) / rate if rate > 0 else 0

            log.info(
                "[Batch %d] analyzed=%d skipped=%d failed=%d | "
                "Total: %d/%d | Rate: %.1f tr/min | ETA: %s",
                batch_num,
                batch_analyzed,
                batch_skipped,
                batch_failed,
                done,
                total,
                rate * 60,
                _fmt_seconds(remaining),
            )

        except Exception as e:
            log.error("[Batch %d] ERROR: %s", batch_num, e, exc_info=True)
            failed += len(batch_ids)
            done += len(batch_ids)

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    log.info("=" * 60)
    log.info("DONE. Total: %d | Failed: %d | Time: %s", total, failed, _fmt_seconds(elapsed))
    log.info("=" * 60)

    await ym_client.close()
    await engine.dispose()


def _apply_worker_env(workers: int, level: int) -> None:
    """Set env vars for worker counts before app modules are imported."""
    if level <= 2:
        os.environ["DJ_AUDIO_TRIAGE_WORKERS"] = str(workers)
    else:
        os.environ["DJ_AUDIO_SCORING_WORKERS"] = str(workers)
        os.environ["DJ_AUDIO_TRIAGE_WORKERS"] = str(min(workers + 4, workers * 2))


def _level_name(level: int) -> str:
    names = {2: "L2/TRIAGE", 3: "L3/SCORING", 4: "L4/TRANSITION", 5: "L5/ADVANCED"}
    return names.get(level, f"L{level}")


def _print_eta(count: int, workers: int, level: int) -> None:
    secs_per_track = {2: 5, 3: 8, 4: 10, 5: 18}.get(level, 10)
    eta_sec = count * secs_per_track / max(workers, 1)
    log.info(
        "Estimated time: %s (assuming %d workers, ~%ds/track)",
        _fmt_seconds(eta_sec),
        workers,
        secs_per_track,
    )


def _fmt_seconds(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f"{h}h {m}m"


if __name__ == "__main__":
    asyncio.run(main())
