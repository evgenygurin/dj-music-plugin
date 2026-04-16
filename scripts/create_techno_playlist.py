"""Create a curated techno playlist in Yandex Music.

Searches for top-quality techno tracks from renowned artists and labels,
creates a new playlist, and populates it. Each search query is tied to
expected artist names to filter out false positives.

Usage:
    python scripts/create_techno_playlist.py [--name "Playlist Name"] [--dry-run]
    python scripts/create_techno_playlist.py --delete-kind 1356  # delete old playlist
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.ym.client import YandexMusicClient
from app.clients.ym.models import YMTrack
from app.clients.ym.rate_limiter import RateLimiter
from app.config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("create_techno")


# ── Artist-verified search queries ──────────────────────────────
# (query, set of expected artist name substrings — case-insensitive)
# If expected_artists is None, accept any result (label/compilation queries)
ARTIST_QUERIES: list[tuple[str, set[str] | None]] = [
    # Peak-time / driving techno
    ("Amelie Lens", {"amelie lens"}),
    ("Charlotte de Witte", {"charlotte de witte"}),
    ("FJAAK techno", {"fjaak"}),
    ("Kobosil techno", {"kobosil"}),
    ("Dax J techno", {"dax j"}),
    ("999999999 techno", {"999999999"}),
    ("Alignment techno", {"alignment"}),
    # Melodic / deep techno
    ("Stephan Bodzin", {"stephan bodzin"}),
    ("Maceo Plex techno", {"maceo plex", "maetrik"}),
    ("Tale Of Us Afterlife", {"tale of us"}),
    ("Recondite techno Acid Pauli", {"recondite"}),
    ("Mind Against techno", {"mind against"}),
    ("Agents Of Time", {"agents of time"}),
    # Hypnotic / minimal
    ("Boris Brejcha", {"boris brejcha"}),
    ("Reinier Zonneveld", {"reinier zonneveld"}),
    ("Enrico Sangiuliano", {"enrico sangiuliano"}),
    ("HI-LO Oliver Heldens techno", {"hi-lo", "oliver heldens"}),
    ("Deborah De Luca techno", {"deborah de luca"}),
    # Industrial / raw
    ("I Hate Models", {"i hate models"}),
    ("SNTS techno", {"snts"}),
    ("Randomer techno", {"randomer"}),
    ("Rebekah techno", {"rebekah"}),
    ("Perc techno", {"perc"}),
    # Acid
    ("Hadone techno", {"hadone"}),
    ("VTSS techno", {"vtss"}),
    ("Introversion techno", {"introversion"}),
    # Detroit / classic
    ("Jeff Mills techno", {"jeff mills"}),
    ("Ben Klock techno", {"ben klock"}),
    ("Marcel Dettmann", {"marcel dettmann"}),
    ("Len Faki techno", {"len faki"}),
    # Drumcode artists
    ("Adam Beyer techno", {"adam beyer"}),
    ("Bart Skils techno", {"bart skils"}),
    # More peak-time
    ("Sara Landry techno", {"sara landry"}),
    ("Mha Iri techno", {"mha iri"}),
    ("Klangkuenstler techno", {"klangkuenstler"}),
    ("T78 techno", {"t78"}),
    ("Lexlay techno", {"lexlay"}),
]

MIN_DURATION_MS = 180_000  # 3 min
MAX_DURATION_MS = 600_000  # 10 min


def _get_artist_names(track: YMTrack) -> list[str]:
    """Extract artist names from track."""
    names: list[str] = []
    for a in track.artists:
        name = str(a.get("name", "")) if isinstance(a, dict) else str(getattr(a, "name", ""))
        if name:
            names.append(name)
    return names


def _matches_expected_artists(track: YMTrack, expected: set[str] | None) -> bool:
    """Check if track has at least one expected artist."""
    if expected is None:
        return True  # label/compilation query, accept anything
    artist_names = [n.lower() for n in _get_artist_names(track)]
    full_str = " ".join(artist_names)
    return any(exp in full_str for exp in expected)


def _is_valid_duration(track: YMTrack) -> bool:
    """Filter by duration."""
    if track.duration_ms is not None:
        return MIN_DURATION_MS <= track.duration_ms <= MAX_DURATION_MS
    return True  # accept if unknown


def _format_track(track: YMTrack) -> str:
    """Human-readable track info."""
    artists = ", ".join(_get_artist_names(track)) or "?"
    if track.duration_ms:
        m, s = divmod(track.duration_ms // 1000, 60)
        return f"{artists} — {track.title} ({m}:{s:02d})"
    return f"{artists} — {track.title}"


async def main(playlist_name: str, dry_run: bool, delete_kind: int | None) -> None:
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
        # Delete old playlist if requested
        if delete_kind is not None:
            log.info("Deleting old playlist kind=%d...", delete_kind)
            await ym.delete_playlist(delete_kind)
            log.info("Deleted.")
            if dry_run:
                return

        # Phase 1: Search with artist verification
        log.info("Searching for quality techno (%d queries)...", len(ARTIST_QUERIES))
        seen_ids: set[str] = set()
        collected: list[YMTrack] = []
        skipped = 0

        for i, (query, expected_artists) in enumerate(ARTIST_QUERIES, 1):
            log.info("  [%d/%d] %s", i, len(ARTIST_QUERIES), query)
            results = await ym.search(query, type="tracks", limit=10)
            batch_ok = 0
            for track in results.tracks:
                if track.id in seen_ids:
                    continue
                if not _is_valid_duration(track):
                    continue
                if not _matches_expected_artists(track, expected_artists):
                    skipped += 1
                    continue
                seen_ids.add(track.id)
                collected.append(track)
                batch_ok += 1
            if batch_ok == 0 and results.tracks:
                log.warning("    No matching tracks (all %d filtered out)", len(results.tracks))

        log.info("Collected %d tracks, skipped %d false positives", len(collected), skipped)

        if not collected:
            log.error("No tracks found")
            return

        # Show results
        log.info("--- Final track list (%d) ---", len(collected))
        for idx, t in enumerate(collected, 1):
            log.info("  %3d. %s", idx, _format_track(t))

        if dry_run:
            log.info("[DRY RUN] Would create '%s' with %d tracks", playlist_name, len(collected))
            return

        # Phase 2: Create playlist
        log.info("Creating playlist '%s'...", playlist_name)
        playlist = await ym.create_playlist(playlist_name, visibility="public")
        log.info("Created: kind=%d", playlist.kind)

        # Phase 3: Resolve track IDs
        track_ids = [t.id for t in collected]
        log.info("Resolving %d track IDs with album info...", len(track_ids))
        resolved = await ym.resolve_track_ids_with_albums(track_ids)

        # Phase 4: Add tracks in batches
        batch_size = 50
        revision = playlist.revision or 0
        kind = playlist.kind
        total_added = 0

        for start in range(0, len(resolved), batch_size):
            batch = resolved[start : start + batch_size]
            log.info("Adding batch %d-%d...", start + 1, start + len(batch))
            await ym.add_tracks_to_playlist(kind, batch, revision)
            updated = await ym.get_playlist(settings.ym_user_id, kind)
            revision = updated.revision or 0
            total_added += len(batch)

        log.info("=== DONE ===")
        log.info("Playlist: %s (%d tracks)", playlist_name, total_added)
        log.info("URL: https://music.yandex.ru/users/%s/playlists/%d", settings.ym_user_id, kind)

    finally:
        await ym.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create curated techno playlist in YM")
    parser.add_argument("--name", default="Quality Techno Selection", help="Playlist name")
    parser.add_argument("--dry-run", action="store_true", help="Search only, don't create")
    parser.add_argument("--delete-kind", type=int, help="Delete playlist by kind before creating")
    args = parser.parse_args()

    asyncio.run(main(args.name, args.dry_run, args.delete_kind))
