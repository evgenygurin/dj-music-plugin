"""Best-effort Beatport genre enrichment during track analysis.

When a track is analyzed (``track_features_analyze`` / ``_reanalyze``), look the
recording up on Beatport and persist its **human-curated genre** plus the
matched Beatport id — but only when an independent audio signal (BPM / duration
we just computed) confirms the match. Failures never break analysis: Beatport
is an optional metadata layer, not a dependency of the audio pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError

log = logging.getLogger(__name__)


def _split_artist_title(track: Any, primary_artist: str | None) -> tuple[str, str]:
    """Derive (artist, title). Our titles are usually ``"Artist - Title"``."""
    raw = (getattr(track, "title", None) or "").strip()
    if " - " in raw:
        artist, _, title = raw.partition(" - ")
        return artist.strip(), title.strip()
    return (primary_artist or "").strip(), raw


async def enrich_beatport_genre(
    ctx: Any,
    uow: UnitOfWork,
    registry: ProviderRegistry | None,
    *,
    track_id: int,
    track: Any,
    features: dict[str, Any],
) -> dict[str, Any] | None:
    """Match the track on Beatport and persist genre. Returns the match or None.

    Silently no-ops when: the provider isn't registered, enrichment is disabled,
    there's no usable title, or nothing matches with sufficient confidence.
    """
    if registry is None or not get_settings().beatport.enrich_on_analyze:
        return None
    try:
        adapter = registry.get("beatport")
    except NotFoundError:
        return None

    primary = await uow.tracks.get_primary_artist_name(track_id)
    artist, title = _split_artist_title(track, primary)
    if not title:
        return None

    params: dict[str, Any] = {"artist": artist, "title": title}
    if features.get("bpm") is not None:
        params["bpm"] = features["bpm"]
    if getattr(track, "duration_ms", None) is not None:
        params["duration_ms"] = track.duration_ms

    try:
        match = await adapter.read("track_match", None, params)
        if not match.get("matched"):
            return None
        # SAVEPOINT around the enrich write so a failure here (DB missing the
        # beatport_* columns, or any flush error) rolls back ONLY this write —
        # never the audio features the analyze handler already flushed into the
        # same UoW. Without it a failed upsert poisons the session and the
        # outer commit discards the whole analysis.
        async with uow.session.begin_nested():
            await uow.track_features.upsert(
                track_id=track_id,
                beatport_genre=match.get("genre"),
                beatport_sub_genre=match.get("sub_genre"),
                beatport_track_id=match.get("beatport_id"),
                beatport_confidence=match.get("confidence"),
            )
        return match
    except Exception as exc:
        log.info("beatport enrich skipped for track %s: %s", track_id, exc)
        return None
