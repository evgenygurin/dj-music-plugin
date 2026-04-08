"""Benchmark script — measures timing of all major operations.

Usage: uv run python scripts/benchmark_operations.py
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

# ── Timing helpers ────────────────────────────────────────────


@dataclass
class TimingResult:
    name: str
    duration_ms: float
    detail: str = ""
    sub_timings: list[TimingResult] = field(default_factory=list)


class Timer:
    def __init__(self, name: str, detail: str = ""):
        self.name = name
        self.detail = detail
        self._start: float = 0

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        self.duration_ms = (time.perf_counter() - self._start) * 1000

    def result(self) -> TimingResult:
        return TimingResult(self.name, self.duration_ms, self.detail)


# ── DB setup ──────────────────────────────────────────────────


@asynccontextmanager
async def make_session():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@asynccontextmanager
async def make_services():
    """Create all services with a shared session."""
    from app.db.repositories.feature import FeatureRepository
    from app.db.repositories.playlist import PlaylistRepository
    from app.db.repositories.set import SetRepository
    from app.db.repositories.track import TrackRepository
    from app.db.repositories.transition import TransitionRepository
    from app.services.set.facade import SetService
    from app.services.track_service import TrackService

    async with make_session() as session:
        track_repo = TrackRepository(session)
        feature_repo = FeatureRepository(session)
        playlist_repo = PlaylistRepository(session)
        set_repo = SetRepository(session)
        transition_repo = TransitionRepository(session)

        track_svc = TrackService(track_repo, feature_repo)
        set_svc = SetService(set_repo, track_repo, playlist_repo, feature_repo, transition_repo)

        yield session, track_svc, set_svc


# ── Benchmarks ────────────────────────────────────────────────


async def bench_list_tracks(track_svc: Any) -> TimingResult:
    with Timer("list_all(limit=100)") as t:
        result = await track_svc.list_all(limit=100)
    t.detail = f"{len(result.items)} tracks returned"
    return t.result()


async def bench_get_track(track_svc: Any) -> TimingResult:
    with Timer("get_track(id=1)") as t:
        track, feat = await track_svc.get_with_features(1)
    t.detail = f"'{track.title}', has_features={feat is not None}"
    return t.result()


async def bench_get_artist_names_batch(track_svc: Any) -> TimingResult:
    track_ids = list(range(1, 31))
    with Timer("get_artist_names_batch(30 tracks)") as t:
        names = await track_svc.get_artist_names_batch(track_ids)
    t.detail = f"{len(names)} tracks with artists"
    return t.result()


async def bench_get_track_features(track_svc: Any) -> TimingResult:
    with Timer("get_track_features(id=1)") as t:
        _, feat = await track_svc.get_with_features(1)
    t.detail = f"features={'found' if feat else 'none'}"
    return t.result()


async def bench_get_features_batch(track_svc: Any) -> TimingResult:
    # Access repo through service internals
    repo = track_svc._features
    track_ids = list(range(1, 31))
    with Timer("get_scoring_features_batch(30 tracks)") as t:
        features = await repo.get_scoring_features_batch(track_ids)
    t.detail = f"{len(features)} tracks with features"
    return t.result()


async def bench_list_playlists(session: Any) -> TimingResult:
    from app.db.repositories.playlist import PlaylistRepository

    repo = PlaylistRepository(session)
    with Timer("list_all(playlists)") as t:
        result = await repo.list_all(limit=20)
    t.detail = f"{len(result.items)} playlists"
    return t.result()


async def bench_get_playlist_with_tracks(session: Any) -> TimingResult:
    from app.db.repositories.playlist import PlaylistRepository

    repo = PlaylistRepository(session)
    track_count = 0
    with Timer("get_playlist(id=1) + load items") as t:
        playlist = await repo.get_with_items(1)
        if playlist and playlist.items:
            track_count = len(playlist.items)
    t.detail = f"{track_count} tracks in playlist"
    return t.result()


async def bench_get_set_summary(set_svc: Any) -> TimingResult:
    with Timer("get_set(view=summary)") as t:
        result = await set_svc.get_set(id=1, view="summary")
    t.detail = f"set '{result['name']}'"
    return t.result()


async def bench_get_set_tracks(set_svc: Any) -> TimingResult:
    with Timer("get_set(view=tracks)") as t:
        result = await set_svc.get_set(id=1, view="tracks")
    t.detail = f"{len(result.get('tracks', []))} tracks"
    return t.result()


async def bench_get_set_full(set_svc: Any) -> TimingResult:
    with Timer("get_set(view=full)") as t:
        result = await set_svc.get_set(id=1, view="full")
    t.detail = f"{len(result.get('tracks', []))} tracks"
    return t.result()


async def bench_build_set_greedy(set_svc: Any) -> TimingResult:
    """Build set with greedy — measures optimizer performance."""
    with Timer("build_set(greedy, 30 tracks)") as t:
        try:
            dj_set, version, quality, algorithm_used = await set_svc.build_set(
                playlist_id=1,
                name="Benchmark Set",
                algorithm="greedy",
                template="classic_60",
            )
            t.detail = f"algorithm={algorithm_used}, score={quality}"
        except Exception as e:
            t.detail = f"error: {type(e).__name__}: {e}"
    return t.result()


async def bench_score_transitions(set_svc: Any) -> TimingResult:
    """Score all transitions for a set."""
    with Timer("score_transitions(set, 30 tracks)") as t:
        try:
            result = await set_svc.score_set_transitions(set_id=1)
            t.detail = f"scored {result.get('scored_transitions', '?')} transitions, avg={result.get('avg_score')}"
        except Exception as e:
            t.detail = f"error: {type(e).__name__}: {e}"
    return t.result()


def _make_ym_client():
    """Create a YM client with proper constructor args."""
    from app.config import settings
    from app.ym.client import YandexMusicClient
    from app.ym.rate_limiter import RateLimiter

    rate_limiter = RateLimiter(
        delay=settings.ym_rate_limit_delay,
        max_retries=settings.ym_retry_attempts,
        backoff_factor=settings.ym_retry_backoff_factor,
    )
    return YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=rate_limiter,
    )


async def bench_ym_search() -> TimingResult:
    client = _make_ym_client()
    with Timer("ym_search('techno', type=tracks, limit=10)") as t:
        try:
            result = await client.search("techno", type="tracks", limit=10)
            t.detail = f"{len(result.tracks)} tracks found"
        except Exception as e:
            t.detail = f"error: {type(e).__name__}: {e}"
        finally:
            await client.close()
    return t.result()


async def bench_ym_get_tracks() -> TimingResult:
    client = _make_ym_client()
    with Timer("ym_get_tracks(5 IDs)") as t:
        try:
            result = await client.get_tracks(
                ["135055088", "121211014", "123713038", "123713036", "127563463"]
            )
            t.detail = f"{len(result)} tracks fetched"
        except Exception as e:
            t.detail = f"error: {type(e).__name__}: {e}"
        finally:
            await client.close()
    return t.result()


async def bench_import_tracks(session: Any, track_svc: Any) -> TimingResult:
    """Measure import of already-existing tracks (idempotent skip)."""
    from app.db.repositories.track import TrackRepository

    repo = TrackRepository(session)
    with Timer("import_tracks(5 existing — skip check)") as t:
        # Just test the resolution/skip path
        count = 0
        for ym_id in ["135055088", "121211014", "123713038", "123713036", "127563463"]:
            existing = await repo.get_by_external_id("yandex_music", ym_id)
            if existing:
                count += 1
    t.detail = f"{count}/5 already exist (skipped)"
    return t.result()


# ── Main ──────────────────────────────────────────────────────


async def main() -> None:
    results: list[TimingResult] = []

    print("=" * 70)
    print("DJ Music Plugin — Performance Benchmark")
    print("=" * 70)

    # --- DB operations ---
    print("\n--- Database Operations ---")
    async with make_services() as (session, track_svc, set_svc):
        for bench in [
            lambda: bench_list_tracks(track_svc),
            lambda: bench_get_track(track_svc),
            lambda: bench_get_artist_names_batch(track_svc),
            lambda: bench_get_track_features(track_svc),
            lambda: bench_get_features_batch(track_svc),
            lambda: bench_list_playlists(session),
            lambda: bench_get_playlist_with_tracks(session),
            lambda: bench_get_set_summary(set_svc),
            lambda: bench_get_set_tracks(set_svc),
            lambda: bench_get_set_full(set_svc),
            lambda: bench_import_tracks(session, track_svc),
        ]:
            r = await bench()
            results.append(r)
            print(f"  {r.duration_ms:8.1f}ms  {r.name}  — {r.detail}")

    # --- Set building ---
    print("\n--- Set Building ---")
    async with make_services() as (session, track_svc, set_svc):
        for bench in [
            lambda: bench_build_set_greedy(set_svc),
            lambda: bench_score_transitions(set_svc),
        ]:
            r = await bench()
            results.append(r)
            print(f"  {r.duration_ms:8.1f}ms  {r.name}  — {r.detail}")

    # --- YM API ---
    print("\n--- Yandex Music API ---")
    for bench in [
        bench_ym_search,
        bench_ym_get_tracks,
    ]:
        r = await bench()
        results.append(r)
        print(f"  {r.duration_ms:8.1f}ms  {r.name}  — {r.detail}")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("SUMMARY — sorted by duration (slowest first)")
    print("=" * 70)
    for r in sorted(results, key=lambda x: x.duration_ms, reverse=True):
        "#" * max(1, int(r.duration_ms / 10))
        category = "SLOW" if r.duration_ms > 500 else "OK" if r.duration_ms > 50 else "FAST"
        print(f"  [{category:4s}] {r.duration_ms:8.1f}ms  {r.name}")

    total = sum(r.duration_ms for r in results)
    print(f"\n  Total: {total:.0f}ms for {len(results)} operations")
    print(f"  Average: {total / len(results):.1f}ms per operation")


if __name__ == "__main__":
    asyncio.run(main())
