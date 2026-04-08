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
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from collections import deque
from typing import Any

# Force line-buffered stdout for real-time `tail -F`.
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
    return p.parse_args()


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


async def _run(args: argparse.Namespace) -> int:
    from app.config import settings
    from app.ym.client import YandexMusicClient
    from app.ym.rate_limiter import RateLimiter

    log.info("=" * 70)
    log.info(
        "YM BFS Expander — source=%d target=%d goal=%d",
        args.source_kind,
        args.target_kind,
        args.target,
    )
    log.info(
        "duration_window=%ds-%ds  batch=%d", args.min_duration_s, args.max_duration_s, args.batch
    )
    log.info("=" * 70)

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

    try:
        # ── Seed from target (idempotent restart) ────────────────
        log.info("loading target playlist state...")
        target_ids, target_revision = await _refresh_playlist(client, owner_id, args.target_kind)
        log.info("target: %d tracks, revision=%d", len(target_ids), target_revision)

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
                    current_count += len(to_add)
                    log.info(
                        "  + added %d tracks → playlist now has %d/%d",
                        len(to_add),
                        current_count,
                        args.target,
                    )
                    # Re-fetch revision after mutation (YM requirement)
                    target_ids, target_revision = await _refresh_playlist(
                        client, owner_id, args.target_kind
                    )
                    current_count = len(target_ids)
                    pending_adds = pending_adds[len(to_add) :]
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
        log.info(
            "elapsed: %.1f min  (%.1f tracks/min)",
            total_elapsed / 60,
            current_count / max(total_elapsed / 60, 0.01),
        )
        log.info("=" * 70)
        return 0
    finally:
        await client.close()


def main() -> None:
    args = _parse_args()
    rc = asyncio.run(_run(args))
    sys.exit(rc)


if __name__ == "__main__":
    main()
