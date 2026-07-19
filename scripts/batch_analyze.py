"""Batch track import + audio analysis — direct API access, no MCP.

Usage:
    uv run python scripts/batch_analyze.py --playlist-id 35 --download
    uv run python scripts/batch_analyze.py --ym-search "techno" --limit 100
    uv run python scripts/batch_analyze.py --analyze-all --limit 500
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.db.session import get_session_factory, dispose
from app.handlers.track_import import track_import_handler
from app.handlers.track_features_analyze import track_features_analyze_handler
from app.handlers.audio_file_download import audio_file_download_handler
from app.providers.yandex.adapter import YandexAdapter
from app.providers.yandex.client import YandexClient
from app.providers.yandex.rate_limiter import TokenBucketRateLimiter
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from sqlalchemy import text as _text

from app.audio.pipeline import AnalysisPipeline
from app.audio.analyzers.base import AnalyzerRegistry


class FakeCtx:
    async def info(self, msg: str) -> None:
        print(f"  [info] {msg}")
    async def report_progress(self, progress: int, total: int, message: str | None = None) -> None:
        print(f"  [{progress}/{total}] {message or ''}")
    async def log(self, level: str, msg: str) -> None:
        print(f"  [{level}] {msg}")


def init_infra() -> tuple[YandexAdapter, ProviderRegistry, AnalysisPipeline]:
    settings = get_settings()

    client = YandexClient(
        token=settings.yandex.token,
        user_id=str(settings.yandex.user_id),
        base_url=settings.yandex.base_url,
        rate_limiter=TokenBucketRateLimiter(
            delay_s=settings.yandex.rate_limit_delay_s,
            max_retries=settings.yandex.retry_attempts,
        ),
    )
    adapter = YandexAdapter(client=client)

    registry = ProviderRegistry()
    registry.register(adapter, default=True)

    analyzer_registry = AnalyzerRegistry()
    with contextlib.suppress(Exception):
        analyzer_registry.discover()
    pipeline = AnalysisPipeline(analyzer_registry)

    print(f"Analyzers available: {analyzer_registry.list_available()}")
    return adapter, registry, pipeline


async def import_ym_playlist(
    playlist_ym_id: str,
    adapter: YandexAdapter,
    registry: ProviderRegistry,
    local_playlist_id: int | None = None,
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Reading YM playlist {playlist_ym_id}...")
    playlist_data = await adapter.read("playlist", id=playlist_ym_id, params={})
    tracks = playlist_data.get("tracks", [])
    if not tracks:
        print("  No tracks found!")
        return {"imported": [], "skipped": [], "errors": []}
    print(f"  {len(tracks)} tracks in playlist")

    external_ids = [str(t["id"]) for t in tracks]
    ctx = FakeCtx()
    factory = get_session_factory()

    async with factory() as session:
        async with UnitOfWork(session) as uow:
            result = await track_import_handler(
                ctx=ctx, uow=uow,
                data={"source": "yandex", "external_ids": external_ids, "playlist_id": local_playlist_id},
                registry=registry,
            )

    imported = len(result.get("imported", []))
    skipped = len(result.get("skipped", []))
    errors = len(result.get("errors", []))
    print(f"  Imported: {imported}, Skipped: {skipped}, Errors: {errors}")
    for err in result.get("errors", [])[:3]:
        print(f"    Error: {err}")
    return result


async def download_audio_batch(
    track_ids: list[int],
    adapter: YandexAdapter,
    registry: ProviderRegistry,
    concurrency: int = 3,
) -> tuple[int, int]:
    """Download audio for tracks that don't have files yet."""
    print(f"\n{'='*60}")
    print(f"Downloading audio for {len(track_ids)} tracks (concurrency={concurrency})...")
    ctx = FakeCtx()
    factory = get_session_factory()
    sem = asyncio.Semaphore(concurrency)
    downloaded = 0
    failed = 0

    async def download_one(tid: int) -> None:
        nonlocal downloaded, failed
        async with sem:
            try:
                async with factory() as session:
                    async with UnitOfWork(session) as uow:
                        result = await audio_file_download_handler(
                            ctx=ctx, uow=uow,
                            data={"track_ids": [tid], "source": "yandex", "skip_existing": True},
                            registry=registry,
                        )
                dn = len(result.get("downloaded", []))
                sk = len(result.get("skipped", []))
                if dn > 0:
                    nonlocal downloaded
                    downloaded += 1
                    print(f"  OK track={tid}")
                elif sk > 0:
                    pass  # already has file
                else:
                    print(f"  SKIP track={tid} (no audio)")
            except Exception as e:
                nonlocal failed
                failed += 1
                if "auth failed" in str(e).lower():
                    print(f"  AUTH ERROR track={tid}: {e}")

    tasks = [download_one(tid) for tid in track_ids]
    await asyncio.gather(*tasks)
    print(f"  Downloaded: {downloaded}, Failed: {failed}")
    return downloaded, failed


async def analyze_tracks_batch(
    track_ids: list[int],
    pipeline: AnalysisPipeline,
    level: int = 2,
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Analyzing {len(track_ids)} tracks (level={level})...")
    ctx = FakeCtx()
    factory = get_session_factory()
    results = {"analyzed": 0, "skipped": 0, "errors": []}

    for i, tid in enumerate(track_ids):
        start = time.time()
        try:
            async with factory() as session:
                async with UnitOfWork(session) as uow:
                    result = await track_features_analyze_handler(
                        ctx=ctx, uow=uow,
                        data={"track_ids": [tid], "level": level},
                        pipeline=pipeline,
                    )
            elapsed = time.time() - start
            if result.get("analyzed"):
                results["analyzed"] += 1
                feat = result.get("features", {})
                print(f"  [{i+1}/{len(track_ids)}] track={tid} bpm={feat.get('bpm','?')} "
                      f"key={feat.get('audio_key_code','?')} mood={feat.get('mood','?')} ({elapsed:.1f}s)")
            else:
                results["skipped"] += 1
                print(f"  [{i+1}/{len(track_ids)}] SKIP track={tid} ({elapsed:.1f}s)")
        except Exception as e:
            elapsed = time.time() - start
            msg = str(e)[:120]
            results["errors"].append({"track_id": tid, "error": msg})
            print(f"  [{i+1}/{len(track_ids)}] ERROR track={tid}: {msg} ({elapsed:.1f}s)")

    print(f"\n  Total: analyzed={results['analyzed']}, skipped={results['skipped']}, errors={len(results['errors'])}")
    return results


async def search_and_import(
    adapter: YandexAdapter,
    registry: ProviderRegistry,
    query: str,
    limit: int = 200,
    import_to_playlist: int | None = None,
) -> list[int]:
    """Search YM, filter electronic by name, import."""
    print(f"\n{'='*60}")
    print(f"Searching YM: '{query}' (limit={limit})...")
    result = await adapter.search(query=query, type="tracks", limit=limit)
    tracks = result.get("tracks", [])

    # Filter by electronic keywords in title + artist
    keywords = [
        "techno", "house", "trance", "dubstep", "dnb", "drum and bass",
        "ambient", "idm", "breaks", "electro", "hardcore", "hardstyle",
        "deep", "progressive", "minimal", "acid", "industrial", "dub",
        "electronic", "club", "rave", "bass", "synth", "beat", "loop",
        "detroit", "berlin", "underground", "mix", "remix", "dj",
        "рейв", "электро", "техно", "хаус", "транс",
    ]
    electronic = []
    for t in tracks:
        title = (t.get("title") or "").lower()
        artists = " ".join(a.get("name", "") for a in (t.get("artists") or []))
        text = f"{title} {artists.lower()}"
        if any(kw in text for kw in keywords):
            electronic.append(t)

    print(f"  Electronic: {len(electronic)} / {len(tracks)} total")

    if not electronic:
        return []

    external_ids = [str(t["id"]) for t in electronic]
    ctx = FakeCtx()
    factory = get_session_factory()

    async with factory() as session:
        async with UnitOfWork(session) as uow:
            result = await track_import_handler(
                ctx=ctx, uow=uow,
                data={"source": "yandex", "external_ids": external_ids, "playlist_id": import_to_playlist},
                registry=registry,
            )

    all_ids = []
    all_ids.extend(m["local_id"] for m in result.get("imported", []))
    all_ids.extend(m["local_id"] for m in result.get("skipped", []))
    print(f"  Imported: {len(result.get('imported',[]))}, Skipped: {len(result.get('skipped',[]))}")
    return all_ids


async def get_unanalyzed_ids(limit: int = 500) -> list[int]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(_text("""
            SELECT t.id FROM tracks t
            WHERE t.id NOT IN (SELECT track_id FROM track_audio_features_computed)
            ORDER BY t.id
            LIMIT :limit
        """), {"limit": limit})
        return [r[0] for r in rows.fetchall()]


async def get_track_ids_without_audio(limit: int = 500) -> list[int]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(_text("""
            SELECT t.id FROM tracks t
            LEFT JOIN dj_library_items li ON li.track_id = t.id
            WHERE li.id IS NULL
            ORDER BY t.id
            LIMIT :limit
        """), {"limit": limit})
        return [r[0] for r in rows.fetchall()]


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch track import + analysis")
    parser.add_argument("--playlist-id", type=int, help="Local playlist ID to sync from YM")
    parser.add_argument("--ym-playlist", type=str, help="YM playlist ID to import")
    parser.add_argument("--ym-search", type=str, help="YM search query for electronic tracks")
    parser.add_argument("--ym-search-continuous", action="store_true", help="Keep searching different queries")
    parser.add_argument("--analyze-all", action="store_true", help="Analyze all unanalyzed tracks")
    parser.add_argument("--analyze-playlist", type=int, help="Analyze tracks from a specific local playlist")
    parser.add_argument("--download", action="store_true", help="Download audio before analyzing")
    parser.add_argument("--download-only", action="store_true", help="Only download, no analysis")
    parser.add_argument("--no-analyze", action="store_true", help="Skip analysis entirely")
    parser.add_argument("--limit", type=int, default=500, help="Max tracks per operation")
    parser.add_argument("--level", type=int, default=2, help="Analysis level (1-4)")
    parser.add_argument("--concurrency", type=int, default=3, help="Download concurrency")
    parser.add_argument("--continuous", action="store_true", help="Keep running until interrupted")
    args = parser.parse_args()

    print("=" * 60)
    print("DJ Music Plugin — Batch Analyzer")
    print("=" * 60)

    adapter, registry, pipeline = init_infra()

    try:
        while True:
            all_track_ids: list[int] = []

            # Phase 1: Import tracks
            if args.playlist_id:
                factory = get_session_factory()
                async with factory() as session:
                    row = (await session.execute(
                        _text("SELECT platform_ids FROM dj_playlists WHERE id = :pid"),
                        {"pid": args.playlist_id},
                    )).first()
                    if row and row[0]:
                        pids = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                        ym_id = pids.get("yandex")
                        if ym_id:
                            result = await import_ym_playlist(
                                playlist_ym_id=str(ym_id), adapter=adapter, registry=registry,
                                local_playlist_id=args.playlist_id,
                            )
                            all_track_ids.extend(m["local_id"] for m in result.get("imported", []))
                            all_track_ids.extend(m["local_id"] for m in result.get("skipped", []))
                        else:
                            print(f"No YM ID for playlist {args.playlist_id}")

            if args.ym_playlist:
                result = await import_ym_playlist(
                    playlist_ym_id=args.ym_playlist, adapter=adapter, registry=registry,
                )
                all_track_ids.extend(m["local_id"] for m in result.get("imported", []))
                all_track_ids.extend(m["local_id"] for m in result.get("skipped", []))

            if args.ym_search:
                ids = await search_and_import(adapter, registry, args.ym_search, limit=args.limit)
                all_track_ids.extend(ids)

            if args.analyze_all:
                ids = await get_unanalyzed_ids(limit=args.limit)
                print(f"\n  Unanalyzed tracks: {len(ids)}")
                all_track_ids.extend(ids)

            if args.analyze_playlist:
                factory = get_session_factory()
                async with factory() as session:
                    rows = await session.execute(_text("""
                        SELECT pi.track_id FROM dj_playlist_items pi
                        WHERE pi.playlist_id = :pid
                        ORDER BY pi.sort_index
                        LIMIT :limit
                    """), {"pid": args.analyze_playlist, "limit": args.limit})
                    all_track_ids.extend(r[0] for r in rows.fetchall())

            # Deduplicate
            all_track_ids = list(dict.fromkeys(all_track_ids))

            if not all_track_ids:
                print("\nNo tracks to process. Idle...")
                if not args.continuous:
                    break
                await asyncio.sleep(5)
                continue

            print(f"\nTotal unique tracks to process: {len(all_track_ids)}")

            # Phase 2: Download audio
            if args.download or args.download_only:
                await download_audio_batch(all_track_ids, adapter, registry, args.concurrency)

            # Phase 3: Analyze
            if not args.no_analyze and not args.download_only:
                # Filter to tracks that have audio files
                factory = get_session_factory()
                async with factory() as session:
                    placeholders = ",".join(f":tid_{i}" for i in range(len(all_track_ids)))
                    params = {f"tid_{i}": tid for i, tid in enumerate(all_track_ids)}
                    params["limit"] = args.limit
                    rows = await session.execute(_text(f"""
                        SELECT t.id FROM tracks t
                        JOIN dj_library_items li ON li.track_id = t.id
                        WHERE t.id IN ({placeholders})
                        AND t.id NOT IN (SELECT track_id FROM track_audio_features_computed)
                        ORDER BY t.id
                        LIMIT :limit
                    """), params)
                    analyzable = [r[0] for r in rows.fetchall()]

                if analyzable:
                    await analyze_tracks_batch(analyzable, pipeline, level=args.level)
                else:
                    print("\nNo tracks ready for analysis (need audio files first)")

            if not args.continuous:
                break

            print("\n--- Next iteration ---")

    finally:
        await adapter.close()
        await dispose()

    print("\n=== DONE ===")


if __name__ == "__main__":
    asyncio.run(main())
