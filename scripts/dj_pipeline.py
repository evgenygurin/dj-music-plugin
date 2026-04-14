"""Full DJ pipeline: import → analyze → classify → audit → build set → score.

Takes a YM playlist, runs the entire DJ Music Plugin pipeline on it,
and produces an optimized DJ set with transition scoring.

Usage:
    python scripts/dj_pipeline.py --ym-kind 1358 --set-name "Techno Set"
    python scripts/dj_pipeline.py --ym-kind 1358 --template peak_hour_60
    python scripts/dj_pipeline.py --ym-kind 1358 --skip-analyze  # if already analyzed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Logging ──────────────────────────────────────────
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("pipeline")

SUB_BATCH = 10  # analyze sub-batch to avoid Supabase session timeout


async def main(args: argparse.Namespace) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.audio.analyzers.base import AnalyzerRegistry
    from app.audio.level_config import AnalysisLevel
    from app.audio.pipeline import AnalysisPipeline
    from app.audio.timeseries import TimeseriesStorage
    from app.clients.ym.client import YandexMusicClient
    from app.clients.ym.rate_limiter import RateLimiter
    from app.config import Settings
    from app.db.repositories.audio import AudioRepository
    from app.db.repositories.feature import FeatureRepository
    from app.db.repositories.ingestion import IngestionRepository
    from app.db.repositories.playlist import PlaylistRepository
    from app.db.repositories.set import SetRepository
    from app.db.repositories.track import TrackRepository
    from app.db.repositories.transition import TransitionRepository
    from app.services.curation.audit import PlaylistAuditService
    from app.services.curation.mood import MoodClassificationService
    from app.services.import_service import ImportService
    from app.services.set.builder import SetBuilderService
    from app.services.set.scoring import SetScoringService
    from app.services.tiered_pipeline import TieredPipeline

    settings = Settings()
    if not settings.ym_token or not settings.ym_user_id:
        log.error("DJ_YM_TOKEN and DJ_YM_USER_ID required")
        sys.exit(1)

    # ── DB engine ────────────────────────────────────
    connect_args: dict[str, Any] = {}
    if settings.database_url.startswith("postgresql"):
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
        connect_args["server_settings"] = {"application_name": "dj_pipeline"}
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=180,
        connect_args=connect_args,
    )
    sf = async_sessionmaker(engine, expire_on_commit=False)

    # ── YM client ────────────────────────────────────
    ym = YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=RateLimiter(
            delay=settings.ym_rate_limit_delay,
            max_retries=settings.ym_retry_attempts,
            backoff_factor=settings.ym_retry_backoff_factor,
        ),
    )

    # ── Analyzer registry ────────────────────────────
    registry = AnalyzerRegistry()
    registry.discover()
    available = sorted(registry.list_available())
    log.info("Analyzers: %s", ", ".join(available))

    timeseries = TimeseriesStorage()
    t_total = time.time()

    try:
        # ═══════════════════════════════════════════════
        # STEP 1: Fetch YM playlist track IDs
        # ═══════════════════════════════════════════════
        log.info("=" * 60)
        log.info("STEP 1: Fetching tracks from YM playlist kind=%d", args.ym_kind)
        log.info("=" * 60)

        playlist_data = await ym.get_playlist(settings.ym_user_id, args.ym_kind)
        log.info("Playlist: '%s' (%d tracks)", playlist_data.title, playlist_data.track_count or 0)

        # Fetch all track IDs (get_playlist_tracks returns full list)
        tracks = await ym.get_playlist_tracks(settings.ym_user_id, args.ym_kind)
        all_ym_ids: list[str] = [str(t.id).split(":")[0] for t in tracks]

        log.info("Fetched %d track IDs from YM", len(all_ym_ids))
        if not all_ym_ids:
            log.error("Empty playlist — nothing to do")
            return

        # ═══════════════════════════════════════════════
        # STEP 2: Import into local DB
        # ═══════════════════════════════════════════════
        log.info("=" * 60)
        log.info("STEP 2: Importing %d tracks into local DB", len(all_ym_ids))
        log.info("=" * 60)
        t0 = time.time()

        async with sf() as session:
            import_svc = ImportService(
                track_repo=TrackRepository(session),
                ym=ym,
                ingestion_repo=IngestionRepository(session),
            )
            import_result = await import_svc.import_tracks(track_refs=all_ym_ids)
            await session.commit()

        id_mapping: dict[str, int] = import_result.get("id_mapping", {})
        local_ids = list(id_mapping.values())
        log.info(
            "Import done in %.1fs: imported=%d, skipped=%d, total_local=%d",
            time.time() - t0,
            import_result.get("imported", 0),
            import_result.get("skipped", 0),
            len(local_ids),
        )

        if not local_ids:
            log.error("No tracks imported — check YM playlist")
            return

        # ═══════════════════════════════════════════════
        # STEP 3: Create local playlist (for build_set)
        # ═══════════════════════════════════════════════
        log.info("=" * 60)
        log.info("STEP 3: Creating local DB playlist")
        log.info("=" * 60)

        playlist_name = args.set_name or playlist_data.title or "Techno Pipeline"
        async with sf() as session:
            # Create playlist
            from app.core.utils.time import utc_now
            from app.db.models.playlist import Playlist

            playlist = Playlist(
                name=f"[Pipeline] {playlist_name}",
                source_of_truth="local",
            )
            session.add(playlist)
            await session.flush()
            local_playlist_id = playlist.id

            # Add tracks to playlist
            for idx, tid in enumerate(local_ids):
                item = PlaylistItem(
                    playlist_id=local_playlist_id,
                    track_id=tid,
                    sort_index=idx,
                    added_at=utc_now(),
                )
                session.add(item)
            await session.commit()
        log.info("Created local playlist id=%d with %d tracks", local_playlist_id, len(local_ids))

        # ═══════════════════════════════════════════════
        # STEP 4: Analyze (L3 = SCORING)
        # ═══════════════════════════════════════════════
        if not args.skip_analyze:
            log.info("=" * 60)
            log.info(
                "STEP 4: Analyzing %d tracks (L3/SCORING) in sub-batches of %d",
                len(local_ids),
                SUB_BATCH,
            )
            log.info("=" * 60)
            t0 = time.time()
            total_analyzed = 0
            total_failed = 0
            total_skipped = 0

            for si in range(0, len(local_ids), SUB_BATCH):
                sub_ids = local_ids[si : si + SUB_BATCH]
                log.info("  Sub-batch %d-%d / %d", si + 1, si + len(sub_ids), len(local_ids))

                async with sf() as session:
                    pipeline = AnalysisPipeline(
                        registry=registry,
                        use_processes=False,
                        max_workers=args.workers or None,
                    )
                    tiered = TieredPipeline(
                        audio_repo=AudioRepository(session),
                        track_repo=TrackRepository(session),
                        pipeline=pipeline,
                        ym_client=ym,
                        timeseries=timeseries,
                    )
                    res = await tiered.ensure_level(
                        sub_ids,
                        AnalysisLevel.SCORING,
                        force=False,
                    )
                    await session.commit()

                total_analyzed += res.get("analyzed", 0)
                total_skipped += res.get("skipped", 0)
                total_failed += res.get("failed", 0)
                log.info(
                    "  Sub-batch done: analyzed=%d, skipped=%d, failed=%d",
                    res.get("analyzed", 0),
                    res.get("skipped", 0),
                    res.get("failed", 0),
                )

            log.info(
                "Analysis done in %.1fs: analyzed=%d, skipped=%d, failed=%d",
                time.time() - t0,
                total_analyzed,
                total_skipped,
                total_failed,
            )
        else:
            log.info("STEP 4: SKIPPED (--skip-analyze)")

        # ═══════════════════════════════════════════════
        # STEP 5: Classify mood (15 techno subgenres)
        # ═══════════════════════════════════════════════
        log.info("=" * 60)
        log.info("STEP 5: Classifying mood for %d tracks", len(local_ids))
        log.info("=" * 60)
        t0 = time.time()

        async with sf() as session:
            mood_svc = MoodClassificationService(
                feature_repo=FeatureRepository(session),
                playlist_repo=PlaylistRepository(session),
            )
            mood_result = await mood_svc.classify_mood(track_ids=local_ids)
            await session.commit()

        log.info(
            "Mood classification done in %.1fs: classified=%d",
            time.time() - t0,
            mood_result.get("classified", 0),
        )
        distribution = mood_result.get("distribution", {})
        if distribution:
            log.info("Subgenre distribution:")
            for mood, count in sorted(distribution.items(), key=lambda x: -x[1]):
                log.info("  %20s: %d tracks", mood, count)

        # ═══════════════════════════════════════════════
        # STEP 6: Audit playlist against techno criteria
        # ═══════════════════════════════════════════════
        log.info("=" * 60)
        log.info("STEP 6: Auditing playlist against techno criteria")
        log.info("=" * 60)
        t0 = time.time()

        async with sf() as session:
            audit_svc = PlaylistAuditService(
                track_repo=TrackRepository(session),
                playlist_repo=PlaylistRepository(session),
                feature_repo=FeatureRepository(session),
            )
            audit_result = await audit_svc.audit_playlist(playlist_id=local_playlist_id)

        stats = audit_result.get("stats", {})
        issues = audit_result.get("issues", [])
        errors = [i for i in issues if i.get("severity") == "error"]
        warnings = [i for i in issues if i.get("severity") == "warning"]

        log.info("Audit done in %.1fs", time.time() - t0)
        log.info(
            "  Tracks: %d (with features: %d)",
            stats.get("total_tracks", 0),
            stats.get("with_features", 0),
        )
        log.info(
            "  BPM range: %.1f - %.1f (mean %.1f)",
            stats.get("bpm_min", 0),
            stats.get("bpm_max", 0),
            stats.get("bpm_mean", 0),
        )
        log.info(
            "  LUFS range: %.1f - %.1f (mean %.1f)",
            stats.get("lufs_min", 0),
            stats.get("lufs_max", 0),
            stats.get("lufs_mean", 0),
        )
        log.info("  Errors: %d, Warnings: %d", len(errors), len(warnings))

        if errors:
            log.warning("  --- ERRORS (tracks failing techno criteria) ---")
            for issue in errors[:20]:
                log.warning(
                    "    Track %d '%s': %s",
                    issue.get("track_id", 0),
                    issue.get("title", "?"),
                    issue.get("issue", ""),
                )
            if len(errors) > 20:
                log.warning("    ... and %d more errors", len(errors) - 20)

        # ═══════════════════════════════════════════════
        # STEP 7: Build optimized DJ set
        # ═══════════════════════════════════════════════
        log.info("=" * 60)
        log.info(
            "STEP 7: Building optimized DJ set (algorithm=%s, template=%s)",
            args.algorithm,
            args.template or "none",
        )
        log.info("=" * 60)
        t0 = time.time()

        async with sf() as session:
            set_builder = SetBuilderService(
                set_repo=SetRepository(session),
                playlist_repo=PlaylistRepository(session),
                feature_repo=FeatureRepository(session),
            )
            dj_set, version, quality_score, algo_used = await set_builder.build_set(
                playlist_id=local_playlist_id,
                name=args.set_name or "Quality Techno Set",
                template=args.template,
                target_duration_min=args.duration,
                algorithm=args.algorithm,
            )
            await session.commit()
            set_id = dj_set.id
            version_id = version.id

        log.info("Set built in %.1fs", time.time() - t0)
        log.info("  Set ID: %d, Version ID: %d", set_id, version_id)
        log.info("  Algorithm: %s", algo_used)
        log.info(
            "  Quality score: %s", f"{quality_score:.3f}" if quality_score is not None else "N/A"
        )

        # ═══════════════════════════════════════════════
        # STEP 8: Score all transitions in the set
        # ═══════════════════════════════════════════════
        log.info("=" * 60)
        log.info("STEP 8: Scoring transitions")
        log.info("=" * 60)
        t0 = time.time()

        async with sf() as session:
            scoring_svc = SetScoringService(
                set_repo=SetRepository(session),
                feature_repo=FeatureRepository(session),
                transition_repo=TransitionRepository(session),
            )
            score_result = await scoring_svc.score_set_transitions(set_id)
            await session.commit()

        transitions = score_result.get("transitions", [])
        hard_conflicts = [t for t in transitions if t.get("hard_reject")]
        avg_score = score_result.get("average_score", 0)
        min_score = score_result.get("min_score", 0)

        log.info("Scoring done in %.1fs", time.time() - t0)
        log.info("  Transitions: %d", len(transitions))
        log.info("  Hard conflicts: %d", len(hard_conflicts))
        log.info("  Average score: %.3f", avg_score or 0)
        log.info("  Min score: %.3f", min_score or 0)

        if transitions:
            log.info("  --- Top 5 transitions ---")
            sorted_tr = sorted(transitions, key=lambda t: t.get("overall", 0), reverse=True)
            for tr in sorted_tr[:5]:
                log.info(
                    "    %.3f: %s → %s (%s)",
                    tr.get("overall", 0),
                    tr.get("from_title", "?"),
                    tr.get("to_title", "?"),
                    tr.get("style", "?"),
                )

            if hard_conflicts:
                log.warning("  --- HARD CONFLICTS ---")
                for tr in hard_conflicts[:10]:
                    log.warning(
                        "    %s → %s: %s",
                        tr.get("from_title", "?"),
                        tr.get("to_title", "?"),
                        tr.get("reject_reason", "?"),
                    )

        # ═══════════════════════════════════════════════
        # SUMMARY
        # ═══════════════════════════════════════════════
        log.info("=" * 60)
        log.info("PIPELINE COMPLETE in %.1fs", time.time() - t_total)
        log.info("=" * 60)
        log.info("  YM playlist: kind=%d (%d tracks)", args.ym_kind, len(all_ym_ids))
        log.info("  Local playlist: id=%d (%d tracks)", local_playlist_id, len(local_ids))
        log.info("  Analyzed: L3/SCORING")
        log.info(
            "  Mood distribution: %s",
            ", ".join(f"{m}={c}" for m, c in sorted(distribution.items(), key=lambda x: -x[1])[:5])
            if distribution
            else "N/A",
        )
        log.info("  Audit: %d errors, %d warnings", len(errors), len(warnings))
        log.info(
            "  DJ Set: id=%d, quality=%.3f, algorithm=%s", set_id, quality_score or 0, algo_used
        )
        log.info(
            "  Transitions: %d scored, %d hard conflicts, avg=%.3f",
            len(transitions),
            len(hard_conflicts),
            avg_score or 0,
        )

    finally:
        await ym.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Full DJ pipeline: import → analyze → classify → audit → build set"
    )
    parser.add_argument("--ym-kind", type=int, required=True, help="YM playlist kind ID")
    parser.add_argument("--set-name", default="Quality Techno Set", help="Name for the DJ set")
    parser.add_argument(
        "--template", default=None, help="Set template (classic_60, peak_hour_60, etc.)"
    )
    parser.add_argument("--duration", type=int, default=None, help="Target duration in minutes")
    parser.add_argument(
        "--algorithm", default="greedy", choices=["greedy", "ga"], help="Optimization algorithm"
    )
    parser.add_argument("--workers", type=int, default=4, help="Analysis workers")
    parser.add_argument(
        "--skip-analyze", action="store_true", help="Skip audio analysis (use existing features)"
    )
    ap = parser.parse_args()

    asyncio.run(main(ap))
