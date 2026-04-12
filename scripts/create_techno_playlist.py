"""Create a curated techno playlist in Yandex Music.

Searches for top-quality techno tracks from renowned artists and labels,
creates a new playlist, and populates it.

Usage:
    python scripts/create_techno_playlist.py [--name "Playlist Name"] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.ym.client import YandexMusicClient
from app.ym.models import YMTrack
from app.ym.rate_limiter import RateLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("create_techno")

# Curated search queries for high-quality techno
# Mix of top artists, labels, and subgenre-specific queries
SEARCH_QUERIES: list[str] = [
    # Peak-time / driving techno
    "Amelie Lens techno",
    "Charlotte de Witte techno",
    "FJAAK",
    "Kobosil",
    "Dax J techno",
    "999999999 techno",
    # Melodic / deep techno
    "Stephan Bodzin",
    "Maceo Plex",
    "Tale Of Us",
    "Recondite",
    "Mind Against",
    # Hypnotic / minimal
    "Boris Brejcha",
    "Reinier Zonneveld",
    "Enrico Sangiuliano",
    "HI-LO techno",
    # Industrial / raw
    "I Hate Models",
    "SNTS techno",
    "AnD techno",
    "Randomer techno",
    # Acid
    "Hadone acid techno",
    "VTSS techno",
    # Labels & compilations
    "Drumcode techno 2025",
    "Afterlife techno",
    "Mord Records techno",
    "Possession techno",
]

# Minimum track duration (3 min) to filter out intros/interludes
MIN_DURATION_MS = 180_000
# Maximum track duration (10 min)
MAX_DURATION_MS = 600_000


def _is_valid_techno_track(track: YMTrack) -> bool:
    """Filter out non-techno or too short/long tracks."""
    if track.duration_ms is not None:
        if track.duration_ms < MIN_DURATION_MS or track.duration_ms > MAX_DURATION_MS:
            return False
    return True


def _track_key(track: YMTrack) -> str:
    """Unique key for deduplication."""
    return track.id


def _format_track(track: YMTrack) -> str:
    """Human-readable track info."""
    artists = ", ".join(
        str(a.get("name", "?")) if isinstance(a, dict) else str(a)
        for a in track.artists
    )
    dur = f" ({track.duration_ms // 1000 // 60}:{track.duration_ms % 60000 // 1000:02d})" if track.duration_ms else ""
    return f"{artists} — {track.title}{dur}"


async def main(playlist_name: str, dry_run: bool) -> None:
    settings = Settings()

    if not settings.ym_token or not settings.ym_user_id:
        log.error("DJ_YM_TOKEN and DJ_YM_USER_ID must be set")
        sys.exit(1)

    rate_limiter = RateLimiter(
        delay=settings.ym_rate_limit_delay,
        max_retries=settings.ym_retry_attempts,
        backoff_factor=settings.ym_retry_backoff_factor,
    )
    ym = YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=rate_limiter,
    )

    try:
        # Phase 1: Search for tracks
        log.info("Searching for quality techno tracks (%d queries)...", len(SEARCH_QUERIES))
        seen_ids: set[str] = set()
        collected: list[YMTrack] = []

        for i, query in enumerate(SEARCH_QUERIES, 1):
            log.info("  [%d/%d] Searching: %s", i, len(SEARCH_QUERIES), query)
            results = await ym.search(query, type="tracks", limit=15)
            for track in results.tracks:
                if track.id not in seen_ids and _is_valid_techno_track(track):
                    seen_ids.add(track.id)
                    collected.append(track)

        log.info("Collected %d unique tracks", len(collected))

        if not collected:
            log.error("No tracks found — check YM token and connectivity")
            return

        # Show what we found
        log.info("--- Track list ---")
        for idx, t in enumerate(collected[:80], 1):
            log.info("  %3d. %s", idx, _format_track(t))
        if len(collected) > 80:
            log.info("  ... and %d more", len(collected) - 80)

        if dry_run:
            log.info("[DRY RUN] Would create playlist '%s' with %d tracks", playlist_name, len(collected))
            return

        # Phase 2: Create playlist
        log.info("Creating playlist '%s'...", playlist_name)
        playlist = await ym.create_playlist(playlist_name, visibility="public")
        log.info("Created playlist kind=%d, revision=%d", playlist.kind, playlist.revision or 0)

        # Phase 3: Resolve track IDs with album info
        track_ids = [t.id for t in collected[:80]]  # YM limit friendly batch
        log.info("Resolving %d track IDs with album info...", len(track_ids))
        resolved = await ym.resolve_track_ids_with_albums(track_ids)

        # Phase 4: Add tracks in batches (50 per batch to be safe)
        batch_size = 50
        revision = playlist.revision or 0
        kind = playlist.kind
        total_added = 0

        for start in range(0, len(resolved), batch_size):
            batch = resolved[start : start + batch_size]
            log.info("Adding batch %d-%d (%d tracks)...", start + 1, start + len(batch), len(batch))
            await ym.add_tracks_to_playlist(kind, batch, revision)

            # Re-fetch for fresh revision
            updated = await ym.get_playlist(settings.ym_user_id, kind)
            revision = updated.revision or 0
            total_added += len(batch)
            log.info("  Batch done. Revision now %d, total added: %d", revision, total_added)

        log.info("=== DONE ===")
        log.info("Playlist: %s", playlist_name)
        log.info("Kind: %d", kind)
        log.info("Tracks added: %d", total_added)
        log.info("YM URL: https://music.yandex.ru/users/%s/playlists/%d", settings.ym_user_id, kind)

    finally:
        await ym.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create curated techno playlist in YM")
    parser.add_argument("--name", default="Quality Techno Selection", help="Playlist name")
    parser.add_argument("--dry-run", action="store_true", help="Search only, don't create")
    args = parser.parse_args()

    asyncio.run(main(args.name, args.dry_run))
