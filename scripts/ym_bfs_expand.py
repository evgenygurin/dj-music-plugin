# PHASE-7 CUTOVER NOTE (2026-04-17):
# This script targets legacy APIs (`app.ym.*`, `app.services.*`, etc.) that
# were deleted in Phase 7 (v0.9/v1.0 architecture migration). It must be
# rewritten against the new v1 surface (`app.providers.yandex.*`,
# `app.repositories.*`) before it can run again. Tracked as BPM-TODO
# post-v1.0.0.
raise NotImplementedError(
    "scripts/ym_bfs_expand.py needs a v1.0.0 rewrite against "
    "app.providers.yandex.* and app.repositories.* — see top-of-file note."
)

"""BFS-expand a YM source playlist via /similar recommendations.

Starts from every track in a source playlist, fetches `ym.get_similar(track)`
for each, filters by techno-compatible heuristics (duration, dedup, not
disliked), adds survivors to a target playlist, then enqueues them for the
next BFS pass. Continues until the target reaches ``--target`` tracks.

Usage:
    uv run python scripts/ym_bfs_expand.py \\
        --source-kind 1113 \\
        --target-kind 1355 \\
        --target 5000

The script is idempotent across restarts: on startup it reads the current
contents of the target playlist and seeds both ``seen`` and ``queue`` from
it, so it only adds NEW tracks.

Optional inline quality gate (``--gate-mode l5``): after every successful
``add_tracks_to_playlist`` batch, imports the tracks into the local DB,
runs ``TieredPipeline.ensure_level(L5)``, checks each track against
techno criteria via ``AudioService.gate_track``, and removes failed tracks
from the YM playlist immediately. This doubles as a quality filter AND
a playlist-overflow workaround: bad tracks vacate their slot before YM's
~10k limit is reached.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import signal
import sys
from collections import deque
from typing import Any

# Force line-buffered stdout for real-time `tail -F`.
with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

log = logging.getLogger("bfs")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--source-kind",
        type=int,
        default=1113,
        help="YM playlist kind to seed the BFS from (default: 1113 = Techno 2025)",
    )
    p.add_argument(
        "--target-kind",
        type=int,
        default=1355,
        help="YM playlist kind to append to (default: 1355 = Techno 2 Mega Boost)",
    )
    p.add_argument(
        "--target",
        type=int,
        default=5000,
        help="Stop once the target playlist has this many tracks (default: 5000)",
    )
    p.add_argument(
        "--min-duration-s",
        type=int,
        default=240,
        help="Minimum track duration in seconds (default: 240 = 4 min)",
    )
    p.add_argument(
        "--max-duration-s",
        type=int,
        default=900,
        help="Maximum track duration in seconds (default: 900 = 15 min)",
    )
    p.add_argument(
        "--batch",
        type=int,
        default=50,
        help="How many tracks to accumulate before each add_tracks_to_playlist call",
    )
    p.add_argument(
        "--max-empty-passes",
        type=int,
        default=3,
        help="Stop if the queue empties out this many times in a row",
    )

    # ── Inline gate (L5 analyze + techno criteria + remove) ───────────────
    p.add_argument(
        "--gate-mode",
        choices=["off", "l5"],
        default="off",
        help="Inline quality gate: off (legacy) or l5 (analyze+gate+remove per batch)",
    )
    p.add_argument(
        "--analyze-workers",
        type=int,
        default=6,
        help="Parallel audio analyze workers for L5 gate stage (default: 6)",
    )
    p.add_argument(
        "--analyze-sub-batch",
        type=int,
        default=10,
        help="Sub-batch size for TieredPipeline.ensure_level — keeps each DB "
        "session under Supabase idle-prune window (default: 10)",
    )
    p.add_argument(
        "--dry-run-gate",
        action="store_true",
        help="Analyze and gate-check, but DO NOT remove failed tracks from YM playlist",
    )
    p.add_argument(
        "--keep-unanalyzed",
        action="store_true",
        help="If L5 analyze fails for a track (download error, corrupt MP3), "
        "keep it in playlist instead of removing it (default: remove unanalyzed)",
    )
    p.add_argument(
        "--pre-gate-existing",
        action="store_true",
        help="Before BFS, run L5+gate+remove on all EXISTING tracks in the "
        "target playlist. Frees slots in a full playlist before BFS starts "
        "adding. Requires --gate-mode l5.",
    )
    p.add_argument(
        "--pre-gate-only",
        action="store_true",
        help="Run pre-gate on the existing target playlist, then EXIT without "
        "running BFS. Use for one-shot quality cleanup of an existing playlist. "
        "Requires --gate-mode l5.",
    )

    p.add_argument(
        "--analyze-orphans-first",
        action="store_true",
        help="Before BFS: find tracks in DB with analysis_level<5 (or no "
        "features at all), run _gate_stage on them to bring to L5, archive "
        "gate-failures. Requires --db-only --gate-mode l5.",
    )

    # ── DB-only mode (no YM playlist mutations) ──────────────────────────
    p.add_argument(
        "--db-only",
        action="store_true",
        help="DB-expansion mode: do NOT add/remove tracks from any YM playlist. "
        "Seed BFS from --source-kind + existing DB tracks. Import+L5+gate each "
        "batch. Failed tracks are archived in DB (status=1). Stop when total "
        "techno tracks in DB >= --target. Requires --gate-mode l5.",
    )

    # Gate criteria overrides (all optional — default to settings.techno_*)
    p.add_argument("--gate-bpm-min", type=float, default=None)
    p.add_argument("--gate-bpm-max", type=float, default=None)
    p.add_argument("--gate-lufs-min", type=float, default=None)
    p.add_argument("--gate-lufs-max", type=float, default=None)
    p.add_argument("--gate-kick-min", type=float, default=None)
    p.add_argument("--gate-hp-ratio-max", type=float, default=None)
    p.add_argument(
        "--gate-tempo-conf-min",
        type=float,
        default=None,
        help="Override techno_tempo_confidence_min. Set to 0.0 to disable "
        "the confidence gate entirely (useful when the BPM detector uses "
        "autocorrelation-based confidence, which is not calibrated to the "
        "legacy 0.3 threshold).",
    )
    p.add_argument(
        "--gate-bpm-stab-min",
        type=float,
        default=None,
        help="Override techno_bpm_stability_min (inter-beat interval CV "
        "coefficient). For real techno this is usually 0.85+.",
    )

    return p.parse_args()


def _build_gate_criteria(args: argparse.Namespace) -> dict[str, float]:
    """Collect non-None CLI overrides into a criteria dict for gate_track."""
    c: dict[str, float] = {}
    if args.gate_bpm_min is not None:
        c["bpm_min"] = args.gate_bpm_min
    if args.gate_bpm_max is not None:
        c["bpm_max"] = args.gate_bpm_max
    if args.gate_lufs_min is not None:
        c["lufs_min"] = args.gate_lufs_min
    if args.gate_lufs_max is not None:
        c["lufs_max"] = args.gate_lufs_max
    if args.gate_kick_min is not None:
        c["kick_min"] = args.gate_kick_min
    if args.gate_hp_ratio_max is not None:
        c["hp_ratio_max"] = args.gate_hp_ratio_max
    if args.gate_tempo_conf_min is not None:
        c["tempo_conf_min"] = args.gate_tempo_conf_min
    if args.gate_bpm_stab_min is not None:
        c["bpm_stab_min"] = args.gate_bpm_stab_min
    return c


def _duration_ok(track_ms: int | None, min_s: int, max_s: int) -> bool:
    if track_ms is None:
        return False
    s = track_ms / 1000.0
    return min_s <= s <= max_s


async def _refresh_playlist(client: Any, owner_id: str, kind: int) -> tuple[list[str], int]:
    """Fetch current playlist track IDs and revision."""
    meta = await client.get_playlist(owner_id=owner_id, kind=kind)
    tracks = await client.get_playlist_tracks(owner_id=owner_id, kind=kind)
    track_ids = [t.id for t in tracks]
    revision = meta.revision or 1
    return track_ids, revision


async def _remove_by_ym_ids(
    client: Any,
    owner_id: str,
    kind: int,
    failed_ym_ids: list[str],
) -> int:
    """Remove tracks from YM playlist by their track ID.

    Fetches current playlist state, finds the indices of failed tracks,
    and deletes them one-by-one in DESCENDING index order so earlier
    removes don't invalidate later indices within the same playlist
    snapshot. Each YM remove mutation increments the revision by 1.
    """
    if not failed_ym_ids:
        return 0

    fresh_ids, rev = await _refresh_playlist(client, owner_id, kind)
    failed_set = set(failed_ym_ids)
    indices = sorted(
        [i for i, tid in enumerate(fresh_ids) if tid in failed_set],
        reverse=True,
    )
    if not indices:
        return 0

    removed = 0
    for idx in indices:
        try:
            await client.remove_tracks_from_playlist(
                kind=kind,
                from_idx=idx,
                to_idx=idx + 1,
                revision=rev,
            )
            rev += 1
            removed += 1
        except Exception as exc:
            log.error(
                "  remove idx=%d failed: %s — refreshing revision and retrying once", idx, exc
            )
            try:
                _, rev = await _refresh_playlist(client, owner_id, kind)
                await client.remove_tracks_from_playlist(
                    kind=kind,
                    from_idx=idx,
                    to_idx=idx + 1,
                    revision=rev,
                )
                rev += 1
                removed += 1
            except Exception as exc2:
                log.error("  remove idx=%d retry failed: %s — skipping", idx, exc2)
    return removed


async def _pre_gate_existing(
    *,
    target_ids: list[str],
    session_factory: Any,
    registry: Any,
    ym_client: Any,
    owner_id: str,
    kind: int,
    batch_size: int,
    workers: int,
    sub_batch: int,
    criteria: dict[str, float],
    keep_unanalyzed: bool,
    dry_run: bool,
    totals: dict[str, int],
    stop_flag: dict[str, bool],
) -> int:
    """One-shot pre-gate pass over existing target playlist tracks.

    Chunks the existing tracks into batches of ``batch_size``, runs
    ``_gate_stage`` on each, and removes failed tracks from the YM
    playlist (unless ``dry_run``). Updates ``totals`` in place so the
    running summary reflects pre-gate work. Honors ``stop_flag`` for
    clean shutdown mid-sweep.

    Returns the total number of tracks removed.
    """
    total = len(target_ids)
    total_removed = 0
    t_start = asyncio.get_event_loop().time()

    for i in range(0, total, batch_size):
        if stop_flag["stop"]:
            log.warning("pre-gate: stop requested after %d/%d", i, total)
            break

        batch = target_ids[i : i + batch_size]
        log.info(
            "pre-gate batch %d/%d (%d tracks)",
            i // batch_size + 1,
            (total + batch_size - 1) // batch_size,
            len(batch),
        )

        failed_ym, stage_stats = await _gate_stage(
            batch,
            session_factory=session_factory,
            registry=registry,
            ym_client=ym_client,
            workers=workers,
            sub_batch=sub_batch,
            criteria=criteria,
            keep_unanalyzed=keep_unanalyzed,
        )
        totals["gate_pass"] += stage_stats["gate_pass"]
        totals["gate_fail"] += stage_stats["gate_fail"]
        totals["gate_unanalyzed"] += stage_stats["gate_unanalyzed"]

        removed = 0
        if failed_ym and not dry_run:
            removed = await _remove_by_ym_ids(ym_client, owner_id, kind, list(failed_ym))
            total_removed += removed
            totals["removed"] += removed

        elapsed_min = (asyncio.get_event_loop().time() - t_start) / 60
        rate = (i + len(batch)) / max(elapsed_min, 0.01)
        log.info(
            "  pre-gate batch: imp=%d skip=%d ana=%d fail=%d "
            "pass=%d gate_fail=%d unana=%d removed=%d "
            "(processed=%d/%d, %.1f tr/min)",
            stage_stats["imported"],
            stage_stats["skipped"],
            stage_stats["analyzed"],
            stage_stats["failed"],
            stage_stats["gate_pass"],
            stage_stats["gate_fail"],
            stage_stats["gate_unanalyzed"],
            removed,
            i + len(batch),
            total,
            rate,
        )

    return total_removed


async def _gate_stage(
    added_ym_ids: list[str],
    *,
    session_factory: Any,
    registry: Any,
    ym_client: Any,
    workers: int,
    sub_batch: int,
    criteria: dict[str, float],
    keep_unanalyzed: bool,
) -> tuple[set[str], dict[str, int]]:
    """Import + L5 analyze + gate-check a freshly-added batch.

    Returns (failed_ym_ids, stats) where stats has keys imported/skipped/
    analyzed/failed/gate_pass/gate_fail/gate_unanalyzed. The caller decides
    whether to actually remove failed tracks (respecting --dry-run-gate).
    """
    import time

    from app.audio.level_config import AnalysisLevel
    from app.audio.pipeline import AnalysisPipeline
    from app.audio.timeseries import TimeseriesStorage
    from app.db.repositories.audio import AudioRepository
    from app.db.repositories.ingestion import IngestionRepository
    from app.db.repositories.track import TrackRepository
    from app.services.audio_service import AudioService
    from app.services.import_service import ImportService
    from app.services.tiered_pipeline import TieredPipeline

    stats = {
        "imported": 0,
        "skipped": 0,
        "analyzed": 0,
        "failed": 0,
        "gate_pass": 0,
        "gate_fail": 0,
        "gate_unanalyzed": 0,
    }
    failed_ym: set[str] = set()

    timeseries_storage = TimeseriesStorage()

    # ── Step 1: import YM IDs → local DB (idempotent) ────────────────────
    t_import = time.time()
    async with session_factory() as session:
        track_repo = TrackRepository(session)
        ingestion_repo = IngestionRepository(session)
        import_svc = ImportService(
            track_repo=track_repo,
            ym=ym_client,
            ingestion_repo=ingestion_repo,
        )
        import_result = await import_svc.import_tracks(track_refs=added_ym_ids)
        await session.commit()

    stats["imported"] = import_result.get("imported", 0)
    stats["skipped"] = import_result.get("skipped", 0)
    ym_to_local: dict[str, int] = import_result.get("id_mapping") or {}
    local_ids = list(ym_to_local.values())
    log.info(
        "    step1 import done in %.1fs — imp=%d skip=%d → %d local_ids",
        time.time() - t_import,
        stats["imported"],
        stats["skipped"],
        len(local_ids),
    )
    if not local_ids:
        return failed_ym, stats

    # ── Step 2: L5 analyze in sub-batches (session lifecycle safety) ─────
    total_ids = len(local_ids)
    counters = {"done": 0, "ok": 0, "fail": 0, "skip": 0}
    log_lock = asyncio.Lock()
    t_analyze = time.time()

    for sub_i in range(0, total_ids, sub_batch):
        sub_ids = local_ids[sub_i : sub_i + sub_batch]
        t_sub = time.time()
        async with session_factory() as session:
            audio_repo = AudioRepository(session)
            track_repo = TrackRepository(session)
            pipeline = AnalysisPipeline(
                registry=registry,
                use_processes=False,
                max_workers=workers,
            )
            tiered = TieredPipeline(
                audio_repo=audio_repo,
                track_repo=track_repo,
                pipeline=pipeline,
                ym_client=ym_client,
                timeseries=timeseries_storage,
            )

            # Wrap _download_and_analyze for per-track progress (like
            # vm_import_and_analyze.py). Lock ensures counter + log line
            # stay consistent under concurrent worker dispatch. `_orig`
            # is bound via default arg to avoid late-binding in the loop.
            async def _wrapped(
                track_id: int,
                ym_track_id: str,
                level_arg: Any,
                _orig: Any = tiered._download_and_analyze,
            ) -> Any:
                _t = time.time()
                res: Any = None
                try:
                    res = await _orig(track_id, ym_track_id, level_arg)
                    return res
                finally:
                    async with log_lock:
                        counters["done"] += 1
                        ok = res is not None
                        counters["ok" if ok else "fail"] += 1
                        log.info(
                            "    [%d/%d] ana local=%d ym=%s %s in %.1fs (ok=%d fail=%d)",
                            counters["done"],
                            total_ids,
                            track_id,
                            ym_track_id,
                            "OK" if ok else "FAIL",
                            time.time() - _t,
                            counters["ok"],
                            counters["fail"],
                        )

            tiered._download_and_analyze = _wrapped  # type: ignore[assignment,method-assign]

            try:
                res = await tiered.ensure_level(sub_ids, AnalysisLevel.ADVANCED)
                await session.commit()
                sub_analyzed = res.get("analyzed", 0)
                sub_skipped = res.get("skipped", 0)
                sub_failed = res.get("failed", 0)
                stats["analyzed"] += sub_analyzed
                stats["failed"] += sub_failed
                counters["skip"] += sub_skipped
                log.info(
                    "    sub-batch %d-%d done in %.1fs: ana=%d skip=%d fail=%d",
                    sub_i + 1,
                    min(sub_i + sub_batch, total_ids),
                    time.time() - t_sub,
                    sub_analyzed,
                    sub_skipped,
                    sub_failed,
                )
            except Exception as exc:
                await session.rollback()
                log.error("  TieredPipeline error: %s", exc, exc_info=True)
                stats["failed"] += len(sub_ids)

    log.info(
        "    step2 analyze done in %.1fs — total: ok=%d skip=%d fail=%d",
        time.time() - t_analyze,
        counters["ok"],
        counters["skip"],
        counters["fail"],
    )

    # ── Step 3: gate-check each track (DB read) ──────────────────────────
    async with session_factory() as session:
        audio_repo = AudioRepository(session)
        audio_svc = AudioService(repo=audio_repo, registry=registry)
        for ym_id, local_id in ym_to_local.items():
            try:
                gate_res = await audio_svc.gate_track(local_id, criteria=criteria)
            except Exception as exc:
                log.error("  gate_track(%d) failed: %s", local_id, exc)
                if not keep_unanalyzed:
                    failed_ym.add(ym_id)
                    stats["gate_unanalyzed"] += 1
                continue

            passed = gate_res.get("passed")
            reasons = gate_res.get("reasons") or []
            if passed is True:
                stats["gate_pass"] += 1
                log.info("    gate local=%d ym=%s PASS", local_id, ym_id)
            elif passed is False:
                stats["gate_fail"] += 1
                failed_ym.add(ym_id)
                log.info(
                    "    gate local=%d ym=%s FAIL reasons=%s",
                    local_id,
                    ym_id,
                    ",".join(reasons),
                )
            else:  # passed is None → no_features
                stats["gate_unanalyzed"] += 1
                if not keep_unanalyzed:
                    failed_ym.add(ym_id)
                log.info(
                    "    gate local=%d ym=%s UNANALYZED reasons=%s keep=%s",
                    local_id,
                    ym_id,
                    ",".join(reasons),
                    keep_unanalyzed,
                )

    return failed_ym, stats


async def _load_orphan_ym_ids(session_factory: Any) -> list[str]:
    """Find active tracks that aren't at L5 yet.

    Returns their YM external IDs (one per track). Tracks with no features
    row at all AND tracks with analysis_level < 5 both qualify. Used by
    --analyze-orphans-first to finish incomplete analysis before BFS
    starts expanding the library.
    """
    from sqlalchemy import select

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track, TrackExternalId

    async with session_factory() as session:
        rows = await session.execute(
            select(TrackExternalId.external_id)
            .join(Track, Track.id == TrackExternalId.track_id)
            .outerjoin(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == Track.id,
            )
            .where(
                Track.status == 0,
                TrackExternalId.platform == "yandex_music",
                (TrackAudioFeaturesComputed.track_id.is_(None))
                | (TrackAudioFeaturesComputed.analysis_level < 5),
            )
            .distinct()
        )
        return [row[0] for row in rows.all()]


async def _load_seen_from_db(session_factory: Any) -> set[str]:
    """Load ALL YM external IDs currently in DB for BFS dedup."""
    from sqlalchemy import select

    from app.db.models.track import TrackExternalId

    async with session_factory() as session:
        rows = await session.execute(
            select(TrackExternalId.external_id).where(TrackExternalId.platform == "yandex_music")
        )
        return {row[0] for row in rows.all()}


async def _count_techno_in_db(session_factory: Any) -> int:
    """Count active L5-analyzed tracks in DB (our proxy for 'techno').

    Failed gate tracks get archived (status=1), so status=0 + L5 features
    is an accurate count of tracks that passed the techno gate OR were
    already valid techno before BFS touched them.
    """
    from sqlalchemy import func, select

    from app.db.models.audio import TrackAudioFeaturesComputed
    from app.db.models.track import Track

    async with session_factory() as session:
        result = await session.execute(
            select(func.count(Track.id.distinct()))
            .join(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == Track.id,
            )
            .where(
                Track.status == 0,
                TrackAudioFeaturesComputed.analysis_level >= 3,
            )
        )
        return int(result.scalar_one() or 0)


async def _archive_failed_in_db(
    session_factory: Any,
    failed_ym_ids: list[str],
) -> int:
    """Archive tracks by their YM external IDs (sets Track.status=1).

    Used instead of _remove_by_ym_ids in db-only mode: failed-gate tracks
    stay in DB (so their YM ID still blocks BFS rediscovery via `seen`),
    but their status flips to archived so they don't count toward the
    techno target and don't show up in set-building queries.
    """
    if not failed_ym_ids:
        return 0

    from sqlalchemy import select, update

    from app.db.models.track import Track, TrackExternalId

    async with session_factory() as session:
        rows = await session.execute(
            select(TrackExternalId.track_id).where(
                TrackExternalId.platform == "yandex_music",
                TrackExternalId.external_id.in_(failed_ym_ids),
            )
        )
        track_ids = [row[0] for row in rows.all()]
        if not track_ids:
            return 0
        await session.execute(update(Track).where(Track.id.in_(track_ids)).values(status=1))
        await session.commit()
        return len(track_ids)


async def _warmup_librosa_jit() -> None:
    """Pre-compile numba JIT on main thread before parallel analyze starts.

    Without this, multiple worker threads race the first-time JIT compilation
    inside numba's C layer → SIGSEGV. See docs/vm-deployment.md troubleshooting.
    """
    import time as _time

    log.info("warming up numba/librosa JIT (one-time, ~10-30s)...")
    _t0 = _time.time()
    try:
        import librosa
        import numpy as np

        sr = 22050
        y = np.random.RandomState(42).randn(sr * 5).astype(np.float32) * 0.1
        librosa.onset.onset_strength(y=y, sr=sr)
        librosa.beat.beat_track(y=y, sr=sr)
        librosa.feature.chroma_cqt(y=y, sr=sr)
        librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        librosa.feature.spectral_centroid(y=y, sr=sr)
        log.info("JIT warmup done in %.1fs", _time.time() - _t0)
    except Exception as exc:
        log.warning("JIT warmup skipped: %s", exc)


async def _run_db_only(
    *,
    args: argparse.Namespace,
    client: Any,
    owner_id: str,
    session_factory: Any,
    registry: Any,
    gate_criteria: dict[str, float],
    totals: dict[str, int],
    stop_flag: dict[str, bool],
) -> int:
    """BFS expansion in DB-only mode.

    Seeds from source playlist + existing DB tracks. Each batch is
    imported into DB, L5-analyzed, gate-checked. Failed tracks are
    archived (Track.status=1) instead of removed from any YM playlist.
    Stops when (initial techno count + gate_pass this session) >= target.
    """
    log.info("═" * 70)
    log.info("DB-ONLY MODE: no YM playlist mutations")
    log.info("═" * 70)

    # ── Orphan analysis pass (bring non-L5 tracks up to L5 first) ────────
    if args.analyze_orphans_first:
        log.info("═" * 70)
        log.info("ORPHAN PASS: analyzing tracks with analysis_level<5")
        log.info("═" * 70)
        orphans = await _load_orphan_ym_ids(session_factory)
        log.info("found %d orphan tracks (no features or level<5)", len(orphans))

        if orphans:
            for i in range(0, len(orphans), args.batch):
                if stop_flag["stop"]:
                    log.warning("orphan pass: stop requested at %d/%d", i, len(orphans))
                    break
                chunk = orphans[i : i + args.batch]
                log.info(
                    "orphan batch %d/%d (%d tracks)",
                    i // args.batch + 1,
                    (len(orphans) + args.batch - 1) // args.batch,
                    len(chunk),
                )
                failed_ym, stage_stats = await _gate_stage(
                    chunk,
                    session_factory=session_factory,
                    registry=registry,
                    ym_client=client,
                    workers=args.analyze_workers,
                    sub_batch=args.analyze_sub_batch,
                    criteria=gate_criteria,
                    keep_unanalyzed=args.keep_unanalyzed,
                )
                totals["gate_pass"] += stage_stats["gate_pass"]
                totals["gate_fail"] += stage_stats["gate_fail"]
                totals["gate_unanalyzed"] += stage_stats["gate_unanalyzed"]

                archived = 0
                if failed_ym and not args.dry_run_gate:
                    archived = await _archive_failed_in_db(session_factory, list(failed_ym))
                    totals["removed"] += archived

                log.info(
                    "  orphan batch: imp=%d skip=%d ana=%d fail=%d "
                    "pass=%d gate_fail=%d unana=%d archived=%d",
                    stage_stats["imported"],
                    stage_stats["skipped"],
                    stage_stats["analyzed"],
                    stage_stats["failed"],
                    stage_stats["gate_pass"],
                    stage_stats["gate_fail"],
                    stage_stats["gate_unanalyzed"],
                    archived,
                )

        after = await _count_techno_in_db(session_factory)
        log.info("ORPHAN PASS done — techno now %d", after)

        if stop_flag["stop"]:
            log.warning("stopping before BFS due to signal")
            return 0

    # ── Bootstrap dedup set and starting count from DB ───────────────────
    log.info("loading existing YM IDs from DB for dedup...")
    seen = await _load_seen_from_db(session_factory)
    log.info("seen: %d YM IDs already in DB", len(seen))

    initial_techno = await _count_techno_in_db(session_factory)
    log.info("initial techno in DB: %d (L5-analyzed, active)", initial_techno)

    if initial_techno >= args.target:
        log.info("already at/above target %d — nothing to do", args.target)
        return 0

    # Merge disliked so we skip known garbage
    try:
        disliked: set[str] = await client.get_disliked_ids()
        log.info("disliked: %d tracks (will be filtered)", len(disliked))
        seen |= disliked
    except Exception as exc:
        log.warning("couldn't fetch disliked: %s — continuing without filter", exc)

    # ── Seed BFS queue from source playlist ──────────────────────────────
    log.info("loading source playlist %d...", args.source_kind)
    source_tracks = await client.get_playlist_tracks(owner_id=owner_id, kind=args.source_kind)
    log.info("source: %d tracks", len(source_tracks))

    queue: deque[str] = deque()
    for t in source_tracks:
        if t.id not in seen:
            queue.append(t.id)
    # Also re-seed BFS from already-known DB tracks (wider graph on restarts)
    for ym_id in list(seen)[:500]:
        queue.append(ym_id)
    log.info("initial queue: %d tracks", len(queue))

    # ── BFS loop ─────────────────────────────────────────────────────────
    pending_adds: list[str] = []
    empty_passes = 0
    similar_calls = 0
    processed = 0
    t_start = asyncio.get_event_loop().time()
    current_count = initial_techno

    while current_count < args.target:
        if stop_flag["stop"]:
            log.warning("stop requested — flushing pending batch")
            break

        if not queue:
            empty_passes += 1
            log.warning("queue empty (pass %d/%d)", empty_passes, args.max_empty_passes)
            if empty_passes >= args.max_empty_passes:
                log.error("queue exhausted — no more candidates")
                break
            # Re-seed: pick any YM ID from seen that we haven't BFS-expanded yet
            for ym_id in list(seen):
                queue.append(ym_id)
            continue

        seed_id = queue.popleft()
        processed += 1
        try:
            similar = await client.get_similar(seed_id)
            similar_calls += 1
        except Exception as exc:
            log.warning("get_similar(%s) failed: %s", seed_id, exc)
            continue

        accepted = 0
        rejected = 0
        for cand in similar:
            if cand.id in seen:
                rejected += 1
                continue
            if not _duration_ok(cand.duration_ms, args.min_duration_s, args.max_duration_s):
                seen.add(cand.id)
                rejected += 1
                continue
            seen.add(cand.id)
            pending_adds.append(cand.id)
            queue.append(cand.id)
            accepted += 1

        elapsed = asyncio.get_event_loop().time() - t_start
        rate = (current_count - initial_techno) / max(elapsed / 60, 0.01)
        log.info(
            "[%d → %d/%d] seed=%s similar=%d ✓%d ✗%d queue=%d pending=%d  %.1f tr/min (net)",
            processed,
            current_count,
            args.target,
            seed_id,
            len(similar),
            accepted,
            rejected,
            len(queue),
            len(pending_adds),
            rate,
        )

        # ── Flush pending batch: import + L5 + gate ──────────────────────
        if len(pending_adds) >= args.batch:
            batch_to_process = pending_adds[:]
            pending_adds = []

            failed_ym, stage_stats = await _gate_stage(
                batch_to_process,
                session_factory=session_factory,
                registry=registry,
                ym_client=client,
                workers=args.analyze_workers,
                sub_batch=args.analyze_sub_batch,
                criteria=gate_criteria,
                keep_unanalyzed=args.keep_unanalyzed,
            )
            totals["added"] += len(batch_to_process)
            totals["gate_pass"] += stage_stats["gate_pass"]
            totals["gate_fail"] += stage_stats["gate_fail"]
            totals["gate_unanalyzed"] += stage_stats["gate_unanalyzed"]
            totals["batches"] += 1

            archived = 0
            if failed_ym and not args.dry_run_gate:
                archived = await _archive_failed_in_db(session_factory, list(failed_ym))
                totals["removed"] += archived

            # Recompute current techno count from DB (authoritative)
            current_count = await _count_techno_in_db(session_factory)

            log.info(
                "  gate batch: imp=%d skip=%d ana=%d fail=%d "
                "pass=%d gate_fail=%d unana=%d archived=%d → techno=%d/%d",
                stage_stats["imported"],
                stage_stats["skipped"],
                stage_stats["analyzed"],
                stage_stats["failed"],
                stage_stats["gate_pass"],
                stage_stats["gate_fail"],
                stage_stats["gate_unanalyzed"],
                archived,
                current_count,
                args.target,
            )

            # Periodic running totals (every 5 batches)
            if totals["batches"] % 5 == 0:
                drop_rate = (
                    100.0 * totals["gate_fail"] / max(totals["gate_pass"] + totals["gate_fail"], 1)
                )
                mins = (asyncio.get_event_loop().time() - t_start) / 60
                effective = (current_count - initial_techno) / max(mins, 0.01)
                log.info(
                    "═ RUNNING TOTALS: added=%d pass=%d fail=%d(%.1f%%) "
                    "archived=%d techno=%d/%d %.1f tr/min (net)",
                    totals["added"],
                    totals["gate_pass"],
                    totals["gate_fail"],
                    drop_rate,
                    totals["removed"],
                    current_count,
                    args.target,
                    effective,
                )

    # ── Flush leftover pending_adds on stop/exit ─────────────────────────
    if pending_adds:
        log.info("final flush: %d pending tracks", len(pending_adds))
        failed_ym, stage_stats = await _gate_stage(
            pending_adds,
            session_factory=session_factory,
            registry=registry,
            ym_client=client,
            workers=args.analyze_workers,
            sub_batch=args.analyze_sub_batch,
            criteria=gate_criteria,
            keep_unanalyzed=args.keep_unanalyzed,
        )
        totals["added"] += len(pending_adds)
        totals["gate_pass"] += stage_stats["gate_pass"]
        totals["gate_fail"] += stage_stats["gate_fail"]
        if failed_ym and not args.dry_run_gate:
            archived = await _archive_failed_in_db(session_factory, list(failed_ym))
            totals["removed"] += archived
        current_count = await _count_techno_in_db(session_factory)

    total_elapsed = asyncio.get_event_loop().time() - t_start
    log.info("=" * 70)
    log.info(
        "DB-ONLY DONE — techno=%d/%d (started at %d), processed %d seeds, %d /similar calls",
        current_count,
        args.target,
        initial_techno,
        processed,
        similar_calls,
    )
    log.info(
        "totals: added=%d pass=%d fail=%d unana=%d archived=%d",
        totals["added"],
        totals["gate_pass"],
        totals["gate_fail"],
        totals["gate_unanalyzed"],
        totals["removed"],
    )
    log.info(
        "elapsed: %.1f min  (%.1f tracks/min net)",
        total_elapsed / 60,
        (current_count - initial_techno) / max(total_elapsed / 60, 0.01),
    )
    log.info("=" * 70)
    return 0


async def _run(args: argparse.Namespace) -> int:
    from app.config import settings
    from app.ym.client import YandexMusicClient
    from app.ym.rate_limiter import RateLimiter

    gate_on = args.gate_mode == "l5"

    if (args.pre_gate_existing or args.pre_gate_only) and not gate_on:
        log.error("--pre-gate-existing / --pre-gate-only require --gate-mode l5")
        return 2

    if args.db_only and not gate_on:
        log.error("--db-only requires --gate-mode l5 (no point importing without gating)")
        return 2

    log.info("=" * 70)
    log.info(
        "YM BFS Expander — source=%d target=%d goal=%d gate_mode=%s",
        args.source_kind,
        args.target_kind,
        args.target,
        args.gate_mode,
    )
    log.info(
        "duration_window=%ds-%ds  batch=%d",
        args.min_duration_s,
        args.max_duration_s,
        args.batch,
    )
    if gate_on:
        log.info(
            "gate: workers=%d sub_batch=%d dry_run=%s keep_unanalyzed=%s",
            args.analyze_workers,
            args.analyze_sub_batch,
            args.dry_run_gate,
            args.keep_unanalyzed,
        )
    log.info("=" * 70)

    # ── Heavy setup for gate mode ────────────────────────────────────────
    session_factory: Any = None
    engine: Any = None
    registry: Any = None
    gate_criteria: dict[str, float] = {}

    if gate_on:
        os.environ.setdefault("DJ_AUDIO_SCORING_WORKERS", str(args.analyze_workers))
        os.environ.setdefault("DJ_AUDIO_TRIAGE_WORKERS", str(args.analyze_workers))

        await _warmup_librosa_jit()

        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.audio.analyzers.base import AnalyzerRegistry

        connect_args: dict[str, Any] = {}
        if settings.database_url.startswith("postgresql"):
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0
            connect_args["server_settings"] = {"application_name": "ym_bfs_expand"}
        engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_recycle=180,
            connect_args=connect_args,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        registry = AnalyzerRegistry()
        registry.discover()
        log.info("analyzers: %s", ", ".join(sorted(registry.list_available())))

        gate_criteria = _build_gate_criteria(args)
        if gate_criteria:
            log.info("gate criteria overrides: %s", gate_criteria)

    client = YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=RateLimiter(
            delay=settings.ym_rate_limit_delay,
            max_retries=settings.ym_retry_attempts,
        ),
    )
    owner_id = settings.ym_user_id

    stop_flag = {"stop": False}

    def _on_signal(signum: int, _frame: Any) -> None:
        log.warning("received signal %d — will stop after current batch", signum)
        stop_flag["stop"] = True

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    # Running totals for periodic summary
    totals = {
        "added": 0,
        "gate_pass": 0,
        "gate_fail": 0,
        "gate_unanalyzed": 0,
        "removed": 0,
        "batches": 0,
    }

    try:
        # ── DB-only mode: no YM playlist mutations ───────────────
        if args.db_only:
            return await _run_db_only(
                args=args,
                client=client,
                owner_id=owner_id,
                session_factory=session_factory,
                registry=registry,
                gate_criteria=gate_criteria,
                totals=totals,
                stop_flag=stop_flag,
            )

        # ── Seed from target (idempotent restart) ────────────────
        log.info("loading target playlist state...")
        target_ids, target_revision = await _refresh_playlist(client, owner_id, args.target_kind)
        log.info("target: %d tracks, revision=%d", len(target_ids), target_revision)

        # ── Pre-gate existing tracks (optional, frees slots) ─────
        if gate_on and (args.pre_gate_existing or args.pre_gate_only):
            log.info("═" * 70)
            log.info(
                "PRE-GATE: running L5+gate on %d existing target tracks (batch=%d, dry_run=%s)",
                len(target_ids),
                args.batch,
                args.dry_run_gate,
            )
            log.info("═" * 70)
            pre_removed = await _pre_gate_existing(
                target_ids=target_ids,
                session_factory=session_factory,
                registry=registry,
                ym_client=client,
                owner_id=owner_id,
                kind=args.target_kind,
                batch_size=args.batch,
                workers=args.analyze_workers,
                sub_batch=args.analyze_sub_batch,
                criteria=gate_criteria,
                keep_unanalyzed=args.keep_unanalyzed,
                dry_run=args.dry_run_gate,
                totals=totals,
                stop_flag=stop_flag,
            )
            # Refresh after pre-gate completes
            target_ids, target_revision = await _refresh_playlist(
                client, owner_id, args.target_kind
            )
            log.info(
                "PRE-GATE done: removed=%d, target now has %d tracks",
                pre_removed,
                len(target_ids),
            )
            if args.pre_gate_only:
                log.info("--pre-gate-only: exiting without BFS expand")
                return 0

        # ── Load disliked set (skip garbage) ─────────────────────
        try:
            disliked: set[str] = await client.get_disliked_ids()
            log.info("disliked: %d tracks (will be filtered)", len(disliked))
        except Exception as exc:
            log.warning("couldn't fetch disliked: %s — continuing without filter", exc)
            disliked = set()

        # ── Seed BFS queue ───────────────────────────────────────
        seen: set[str] = set(target_ids) | disliked
        queue: deque[str] = deque()

        # Existing target tracks become BFS seeds (round 2+)
        for tid in target_ids:
            queue.append(tid)

        # Source playlist supplies the fresh seeds (round 1)
        log.info("loading source playlist %d...", args.source_kind)
        source_tracks = await client.get_playlist_tracks(owner_id=owner_id, kind=args.source_kind)
        log.info("source: %d tracks", len(source_tracks))

        for t in source_tracks:
            if t.id not in seen:
                queue.append(t.id)
        log.info("initial queue: %d tracks, seen: %d", len(queue), len(seen))

        # ── BFS loop ─────────────────────────────────────────────
        current_count = len(target_ids)
        pending_adds: list[str] = []
        empty_passes = 0
        similar_calls = 0
        processed = 0
        t_start = asyncio.get_event_loop().time()

        while current_count < args.target:
            if stop_flag["stop"]:
                log.warning("stop requested — flushing pending batch")
                break

            if not queue:
                empty_passes += 1
                log.warning("queue empty (pass %d/%d)", empty_passes, args.max_empty_passes)
                if empty_passes >= args.max_empty_passes:
                    log.error("queue exhausted — no more candidates")
                    break
                # Re-seed from the newly-added tracks (already in target_ids)
                fresh, _ = await _refresh_playlist(client, owner_id, args.target_kind)
                for tid in fresh:
                    if tid not in seen:
                        seen.add(tid)
                    queue.append(tid)
                continue

            seed_id = queue.popleft()
            processed += 1
            try:
                similar = await client.get_similar(seed_id)
                similar_calls += 1
            except Exception as exc:
                log.warning("get_similar(%s) failed: %s", seed_id, exc)
                continue

            accepted = 0
            rejected = 0
            for cand in similar:
                if cand.id in seen:
                    rejected += 1
                    continue
                if not _duration_ok(cand.duration_ms, args.min_duration_s, args.max_duration_s):
                    seen.add(cand.id)  # remember we rejected it — don't re-check
                    rejected += 1
                    continue
                seen.add(cand.id)
                pending_adds.append(cand.id)
                queue.append(cand.id)  # the new track also gets expanded later
                accepted += 1
                if current_count + len(pending_adds) >= args.target:
                    break

            elapsed = asyncio.get_event_loop().time() - t_start
            rate = (current_count + len(pending_adds)) / max(elapsed / 60, 0.01)
            log.info(
                "[%d → %d/%d] seed=%s similar=%d ✓%d ✗%d queue=%d  %.1f tr/min",
                processed,
                current_count + len(pending_adds),
                args.target,
                seed_id,
                len(similar),
                accepted,
                rejected,
                len(queue),
                rate,
            )

            # ── Flush pending batch ──────────────────────────────
            if len(pending_adds) >= args.batch or (
                current_count + len(pending_adds) >= args.target
            ):
                to_add = pending_adds[: args.target - current_count]
                if not to_add:
                    break
                try:
                    resolved = await client.resolve_track_ids_with_albums(to_add)
                    await client.add_tracks_to_playlist(
                        kind=args.target_kind,
                        track_ids=resolved,
                        revision=target_revision,
                    )
                    log.info(
                        "  + added %d tracks → playlist now has ~%d/%d",
                        len(to_add),
                        current_count + len(to_add),
                        args.target,
                    )
                    totals["added"] += len(to_add)
                    totals["batches"] += 1

                    # Re-fetch revision immediately after add (YM requirement)
                    target_ids, target_revision = await _refresh_playlist(
                        client, owner_id, args.target_kind
                    )
                    current_count = len(target_ids)
                    pending_adds = pending_adds[len(to_add) :]

                    # ── GATE STAGE ───────────────────────────────
                    if gate_on:
                        failed_ym, stage_stats = await _gate_stage(
                            to_add,
                            session_factory=session_factory,
                            registry=registry,
                            ym_client=client,
                            workers=args.analyze_workers,
                            sub_batch=args.analyze_sub_batch,
                            criteria=gate_criteria,
                            keep_unanalyzed=args.keep_unanalyzed,
                        )
                        totals["gate_pass"] += stage_stats["gate_pass"]
                        totals["gate_fail"] += stage_stats["gate_fail"]
                        totals["gate_unanalyzed"] += stage_stats["gate_unanalyzed"]

                        removed = 0
                        if failed_ym and not args.dry_run_gate:
                            removed = await _remove_by_ym_ids(
                                client, owner_id, args.target_kind, list(failed_ym)
                            )
                            totals["removed"] += removed
                            # Refresh after removes so BFS sees correct state
                            target_ids, target_revision = await _refresh_playlist(
                                client, owner_id, args.target_kind
                            )
                            current_count = len(target_ids)

                        log.info(
                            "  gate batch: imp=%d skip=%d ana=%d fail=%d "
                            "pass=%d gate_fail=%d unana=%d removed=%d net=+%d",
                            stage_stats["imported"],
                            stage_stats["skipped"],
                            stage_stats["analyzed"],
                            stage_stats["failed"],
                            stage_stats["gate_pass"],
                            stage_stats["gate_fail"],
                            stage_stats["gate_unanalyzed"],
                            removed,
                            len(to_add) - removed,
                        )

                    # Periodic running totals (every 5 batches)
                    if gate_on and totals["batches"] % 5 == 0:
                        drop_rate = (
                            100.0
                            * totals["gate_fail"]
                            / max(totals["gate_pass"] + totals["gate_fail"], 1)
                        )
                        mins = (asyncio.get_event_loop().time() - t_start) / 60
                        effective = current_count / max(mins, 0.01)
                        log.info(
                            "═ RUNNING TOTALS: added=%d pass=%d fail=%d(%.1f%%) "
                            "removed=%d current=%d/%d %.1f tr/min (net)",
                            totals["added"],
                            totals["gate_pass"],
                            totals["gate_fail"],
                            drop_rate,
                            totals["removed"],
                            current_count,
                            args.target,
                            effective,
                        )

                except Exception as exc:
                    log.error("add_tracks failed: %s — dropping batch", exc)
                    pending_adds = []

        # Flush leftovers on stop
        if pending_adds and current_count < args.target and not stop_flag["stop"]:
            to_add = pending_adds[: args.target - current_count]
            try:
                resolved = await client.resolve_track_ids_with_albums(to_add)
                await client.add_tracks_to_playlist(
                    kind=args.target_kind,
                    track_ids=resolved,
                    revision=target_revision,
                )
                current_count += len(to_add)
                log.info(
                    "  + final flush: %d tracks → %d/%d", len(to_add), current_count, args.target
                )
            except Exception as exc:
                log.error("final flush failed: %s", exc)

        total_elapsed = asyncio.get_event_loop().time() - t_start
        log.info("=" * 70)
        log.info(
            "DONE — target has %d/%d tracks, processed %d seeds, %d /similar calls",
            current_count,
            args.target,
            processed,
            similar_calls,
        )
        if gate_on:
            log.info(
                "gate totals: added=%d pass=%d fail=%d unana=%d removed=%d (dry_run=%s)",
                totals["added"],
                totals["gate_pass"],
                totals["gate_fail"],
                totals["gate_unanalyzed"],
                totals["removed"],
                args.dry_run_gate,
            )
        log.info(
            "elapsed: %.1f min  (%.1f tracks/min)",
            total_elapsed / 60,
            current_count / max(total_elapsed / 60, 0.01),
        )
        log.info("=" * 70)
        return 0
    finally:
        await client.close()
        if engine is not None:
            await engine.dispose()


def main() -> None:
    args = _parse_args()
    rc = asyncio.run(_run(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
