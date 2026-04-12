"""Discovery service — find similar tracks, feedback gate, playlist expansion.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)

from app.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.db.repositories.track import TrackRepository
from app.ym.client import YandexMusicClient
from app.ym.filters import genre_ok, is_excluded_title, ym_track_summary


class DiscoveryService:
    """Track discovery, similar track search, and playlist expansion."""

    def __init__(
        self,
        track_repo: TrackRepository,
        ym: YandexMusicClient,
    ) -> None:
        self._tracks = track_repo
        self._ym = ym

    async def find_similar_ym(
        self,
        track_id: int,
        limit: int = 20,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
        genre_filter_list: list[str] | None = None,
        genre_blacklist_list: list[str] | None = None,
        exclude_patterns_list: list[str] | None = None,
    ) -> dict[str, Any]:
        """Find similar tracks via YM API with declarative filters."""
        track = await self._tracks.get_by_id(track_id)
        if not track:
            raise NotFoundError("Track", track_id)

        ext = await self._tracks.get_external_id(track_id, "yandex_music")
        ym_id = ext.external_id if ext else None

        # Fallback: search by title
        if not ym_id:
            search_result = await self._ym.search(track.title, type="tracks", limit=1)
            if search_result.tracks:
                ym_id = search_result.tracks[0].id
            else:
                return {
                    "track_id": track_id,
                    "track_title": track.title,
                    "strategy": "ym",
                    "similar": [],
                    "message": "Could not find this track on YM",
                }

        raw_similar = await self._ym.get_similar(ym_id)

        min_dur = min_duration_ms or settings.discovery_min_duration_ms
        max_dur = max_duration_ms or settings.discovery_max_duration_ms

        filtered = _apply_discovery_filters(
            raw_similar,
            limit,
            min_dur,
            max_dur,
            genre_filter_list,
            genre_blacklist_list,
            exclude_patterns_list,
        )

        return {
            "track_id": track_id,
            "track_title": track.title,
            "strategy": "ym",
            "ym_id_used": ym_id,
            "total_raw": len(raw_similar),
            "after_filter": len(filtered),
            "similar": filtered,
        }

    async def find_similar_llm(
        self,
        track_id: int,
        queries: list[str],
        limit: int = 20,
        genre_filter_list: list[str] | None = None,
        genre_blacklist_list: list[str] | None = None,
        exclude_patterns_list: list[str] | None = None,
    ) -> dict[str, Any]:
        """LLM-assisted similar track discovery using pre-generated search queries."""
        track = await self._tracks.get_by_id(track_id)
        if not track:
            raise NotFoundError("Track", track_id)

        all_results = []
        for q in queries[:limit]:
            try:
                sr = await self._ym.search(q, type="tracks", limit=3)
                for t in sr.tracks:
                    if not genre_ok(
                        t.albums or [],
                        whitelist=genre_filter_list,
                        blacklist=genre_blacklist_list,
                    ):
                        continue
                    if is_excluded_title(t.title, exclude_patterns_list):
                        continue
                    all_results.append(ym_track_summary(t))
            except Exception:
                logger.debug("YM similar query failed for seed, skipping", exc_info=True)
                continue

        # Dedup by ym_id
        seen: set[str] = set()
        deduped = []
        for r in all_results:
            if r["ym_id"] not in seen:
                seen.add(r["ym_id"])
                deduped.append(r)

        return {
            "track_id": track_id,
            "track_title": track.title,
            "strategy": "llm",
            "queries_used": queries,
            "total_raw": len(all_results),
            "after_filter": len(deduped),
            "similar": deduped[:limit],
        }

    async def filter_by_feedback(
        self,
        ym_track_ids: list[str],
        liked_set: set[str] | None = None,
        disliked_set: set[str] | None = None,
    ) -> dict[str, Any]:
        """Apply liked/disliked feedback gate to YM track IDs."""
        if not ym_track_ids:
            raise ValidationError("ym_track_ids required")

        if liked_set is None or disliked_set is None:
            liked_set, disliked_set = await self.get_feedback_sets()

        result_passed: list[str] = []
        result_blocked: list[str] = []
        result_boosted: list[str] = []

        for tid in ym_track_ids:
            if tid in disliked_set:
                result_blocked.append(tid)
            elif tid in liked_set:
                result_boosted.append(tid)
            else:
                result_passed.append(tid)

        return {
            "total": len(ym_track_ids),
            "passed": result_passed,
            "blocked_disliked": result_blocked,
            "boosted_liked": result_boosted,
            "counts": {
                "passed": len(result_passed),
                "blocked": len(result_blocked),
                "boosted": len(result_boosted),
            },
        }

    async def get_feedback_sets(self) -> tuple[set[str], set[str]]:
        """Fetch liked/disliked sets from YM API."""
        liked_set = await self._ym.get_liked_ids()
        disliked_set = await self._ym.get_disliked_ids()
        return liked_set, disliked_set

    async def expand_playlist_ym(
        self,
        ym_playlist_kind: int,
        target_count: int = 100,
        genre_filter_list: list[str] | None = None,
        genre_blacklist_list: list[str] | None = None,
        exclude_patterns_list: list[str] | None = None,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
        use_feedback: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Expand YM playlist with similar tracks. One-call orchestrator."""
        import time as _time

        _t0 = _time.monotonic()

        # 1. Fetch current playlist
        current = await self._ym.get_playlist_tracks(settings.ym_user_id, ym_playlist_kind)
        existing_ids = {t.id for t in current}
        need = max(0, target_count - len(current))

        if need == 0:
            return {
                "playlist_kind": ym_playlist_kind,
                "current_count": len(current),
                "target_count": target_count,
                "added": 0,
                "message": "Playlist already meets target count",
            }

        # 2. Select seeds
        max_seeds = min(len(current), settings.discovery_max_seeds)
        seeds = random.sample(current, max_seeds) if len(current) > max_seeds else list(current)

        # 3. Feedback gate
        liked: set[str] = set()
        disliked: set[str] = set()
        if use_feedback:
            liked, disliked = await self.get_feedback_sets()

        # 4. Collect candidates
        min_dur = min_duration_ms or settings.discovery_min_duration_ms
        max_dur = max_duration_ms or settings.discovery_max_duration_ms
        candidates: list[dict[str, Any]] = []
        blocked_count = 0

        for seed in seeds:
            if len(candidates) >= need:
                break

            try:
                raw_similar = await self._ym.get_similar(seed.id)
            except Exception:
                logger.debug("YM get_similar failed for seed %s", seed.id, exc_info=True)
                continue

            for t in raw_similar:
                if t.id in existing_ids:
                    continue
                if any(c["ym_id"] == t.id for c in candidates):
                    continue
                if use_feedback and t.id in disliked:
                    blocked_count += 1
                    continue
                dur = t.duration_ms or 0
                if dur and (dur < min_dur or dur > max_dur):
                    continue
                if is_excluded_title(t.title, exclude_patterns_list):
                    continue
                if not genre_ok(
                    t.albums or [],
                    whitelist=genre_filter_list,
                    blacklist=genre_blacklist_list,
                ):
                    continue

                entry = ym_track_summary(t)
                entry["is_liked"] = t.id in liked
                candidates.append(entry)

                if len(candidates) >= need:
                    break

        # 5. Dry run or add
        to_add = candidates[:need]

        if dry_run:
            return {
                "dry_run": True,
                "playlist_kind": ym_playlist_kind,
                "current_count": len(current),
                "target_count": target_count,
                "candidates_found": len(candidates),
                "would_add": len(to_add),
                "blocked_disliked": blocked_count,
                "seeds_used": len(seeds),
                "candidates": to_add[:50],
            }

        # 6. Batch add
        playlist_info = await self._ym.get_playlist(settings.ym_user_id, ym_playlist_kind)
        revision = playlist_info.revision or 1
        added = 0
        batch_size = settings.discovery_batch_size

        for batch_start in range(0, len(to_add), batch_size):
            batch = to_add[batch_start : batch_start + batch_size]
            track_ids_batch = [
                f"{c['ym_id']}:{c['album_id']}" if c.get("album_id") else c["ym_id"] for c in batch
            ]
            try:
                result = await self._ym.add_tracks_to_playlist(
                    ym_playlist_kind,
                    track_ids_batch,
                    revision,
                )
                revision = result.get("revision", revision + 1)
                added += len(batch)
            except Exception:
                logger.warning("YM playlist modify failed, stopping batch add", exc_info=True)
                break

        elapsed_ms = int((_time.monotonic() - _t0) * 1000)

        return {
            "playlist_kind": ym_playlist_kind,
            "before_count": len(current),
            "after_count": len(current) + added,
            "added": added,
            "seeds_used": len(seeds),
            "candidates_found": len(candidates),
            "blocked_disliked": blocked_count,
            "sample_tracks": to_add[:20],
            "execution_time_ms": elapsed_ms,
        }


def _apply_discovery_filters(
    tracks: list[Any],
    limit: int,
    min_dur: int,
    max_dur: int,
    genre_filter_list: list[str] | None,
    genre_blacklist_list: list[str] | None,
    exclude_patterns_list: list[str] | None,
) -> list[dict[str, Any]]:
    """Apply duration/genre/title filters to raw track list."""
    filtered = []
    for t in tracks:
        dur = t.duration_ms or 0
        if dur and (dur < min_dur or dur > max_dur):
            continue
        if is_excluded_title(t.title, exclude_patterns_list):
            continue
        if not genre_ok(
            t.albums or [],
            whitelist=genre_filter_list,
            blacklist=genre_blacklist_list,
        ):
            continue
        filtered.append(ym_track_summary(t))
        if len(filtered) >= limit:
            break
    return filtered
