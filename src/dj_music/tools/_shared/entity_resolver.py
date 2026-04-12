from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.repositories.track import TrackRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EntityRef:
    """Parsed entity reference."""

    type: Literal["id", "ym_id", "query"]
    value: Any  # int for id, str for ym_id/query


def parse_entity_ref(ref: int | str) -> EntityRef:
    """Parse flexible entity reference.

    Supports: numeric ID (42 or "42"), prefixed ("ym:12345"), text query ("Aphex Twin").
    Raises ValueError if empty.
    """
    if isinstance(ref, int):
        return EntityRef(type="id", value=ref)

    ref_str = str(ref).strip()
    if not ref_str:
        raise ValueError("Entity reference cannot be empty")

    # Try numeric
    try:
        return EntityRef(type="id", value=int(ref_str))
    except ValueError:
        pass

    # Try ym: prefix
    if ref_str.startswith("ym:"):
        return EntityRef(type="ym_id", value=ref_str[3:])

    # Default: text query
    return EntityRef(type="query", value=ref_str)


async def resolve_track_refs(
    refs: list[Any],
    session: AsyncSession,
) -> list[int]:
    """Resolve mixed track references to local DB track IDs.

    Accepts: local DB IDs (int), YM track IDs (large ints/strings),
    prefixed ("ym:12345"), text queries ("Artist - Title").

    Returns list of resolved DB track IDs. Unresolvable refs are logged and skipped.
    """
    resolved: list[int] = []
    track_repo = TrackRepository(session)
    for ref in refs:
        parsed = parse_entity_ref(ref)

        if parsed.type == "id":
            db_id = parsed.value
            # Heuristic: YM IDs are typically > 1_000_000, DB IDs are small
            if db_id > 1_000_000:
                # Likely a YM track ID — look up via TrackExternalId
                ym_track_id = await _resolve_ym_id(str(db_id), session)
                if ym_track_id is not None:
                    resolved.append(ym_track_id)
                else:
                    logger.warning("Cannot resolve YM track ID %s to local DB", db_id)
            else:
                # Small ID — assume local DB track ID
                resolved.append(db_id)

        elif parsed.type == "ym_id":
            ym_track_id = await _resolve_ym_id(parsed.value, session)
            if ym_track_id is not None:
                resolved.append(ym_track_id)
            else:
                logger.warning("Cannot resolve ym:%s to local DB", parsed.value)

        elif parsed.type == "query":
            matches = await track_repo.search_by_text(parsed.value, limit=1)
            if matches:
                resolved.append(matches[0].id)
            else:
                logger.warning("Cannot resolve query '%s' to local track", parsed.value)

    return resolved


async def _resolve_ym_id(ym_id: str, session: AsyncSession) -> int | None:
    """Look up local track_id by YM external ID."""
    track_repo = TrackRepository(session)
    ext = await track_repo.get_by_external_id("yandex_music", ym_id)
    return ext.track_id if ext is not None else None
