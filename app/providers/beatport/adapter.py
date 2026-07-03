"""BeatportAdapter — universal Provider protocol over BeatportClient.

Read-only metadata provider. Its job: given a track we already have (title +
artist + audio-detected BPM/duration), return Beatport's human-curated
**genre / sub-genre + authored BPM + Camelot key** for the matched recording.

Entities (``provider_read``):
  * ``track``       — fetch one Beatport track by its Beatport id.
  * ``track_match`` — search + verify; returns the best match with a confidence
                      tier (see matcher). This is the analysis-time entry point.
  * ``account``     — subscription/feature introspection.

Write is unsupported (catalog is read-only). ``download_audio`` raises — audio
needs a paid Beatport Streaming Professional subscription.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from app.providers.beatport.client import BeatportClient, SubscriptionRequiredError
from app.providers.beatport.matcher import pick_best
from app.shared.errors import ValidationError


def normalize_track(t: dict[str, Any]) -> dict[str, Any]:
    """Map a raw Beatport track dict to our compact, stable shape."""
    genre = t.get("genre") or {}
    sub = t.get("sub_genre") or {}
    key = t.get("key") or {}
    release = t.get("release") or {}
    camelot = None
    if key.get("camelot_number") and key.get("camelot_letter"):
        camelot = f"{key['camelot_number']}{key['camelot_letter']}"
    return {
        "beatport_id": t.get("id"),
        "title": t.get("name"),
        "mix_name": t.get("mix_name"),
        "artists": [a.get("name") for a in t.get("artists", []) if a.get("name")],
        "remixers": [a.get("name") for a in t.get("remixers", []) if a.get("name")],
        "genre": genre.get("name"),
        "genre_id": genre.get("id"),
        "sub_genre": sub.get("name") if sub else None,
        "bpm": t.get("bpm"),
        "key": key.get("name"),
        "camelot": camelot,
        "isrc": t.get("isrc"),
        "length_ms": t.get("length_ms"),
        "release": release.get("name"),
        "label": (release.get("label") or {}).get("name"),
        "slug": t.get("slug"),
        "url": t.get("url"),
    }


class BeatportAdapter:
    name: str = "beatport"

    entities_supported: ClassVar[tuple[str, ...]] = ("track", "track_match", "account")
    # Read-only provider — no write operations.
    operations_supported: ClassVar[dict[str, tuple[str, ...]]] = {}

    def __init__(
        self,
        *,
        client: BeatportClient,
        bpm_tolerance: float = 1.5,
        duration_tolerance_ms: int = 3000,
        search_limit: int = 10,
    ) -> None:
        self._client = client
        self._bpm_tol = bpm_tolerance
        self._dur_tol_ms = duration_tolerance_ms
        self._search_limit = search_limit

    # ---------- read ---------- #

    async def read(self, entity: str, id: str | None, params: dict[str, Any]) -> dict[str, Any]:
        match entity:
            case "track":
                if id is None:
                    raise ValidationError("beatport track read requires id")
                return normalize_track(await self._client.get_track(str(id)))
            case "track_match":
                return await self._match(params)
            case "account":
                return await self._client.get_account()
            case _:
                raise ValidationError(f"unknown beatport read entity: {entity}")

    async def _match(self, params: dict[str, Any]) -> dict[str, Any]:
        title = params.get("title")
        artist = params.get("artist") or ""
        if not title:
            raise ValidationError("beatport track_match requires 'title' (and ideally 'artist')")
        bpm = params.get("bpm")
        duration_ms = params.get("duration_ms")
        isrc = params.get("isrc")
        query = " ".join(p for p in (artist, title) if p).strip()
        raw = await self._client.search(
            query=query, type="tracks", per_page=int(params.get("limit", self._search_limit))
        )
        candidates = [normalize_track(t) for t in (raw.get("tracks") or [])]
        result = pick_best(
            candidates=candidates,
            title=title,
            artist=artist,
            bpm=float(bpm) if bpm is not None else None,
            duration_ms=int(duration_ms) if duration_ms is not None else None,
            isrc=isrc,
            bpm_tol=self._bpm_tol,
            dur_tol_ms=self._dur_tol_ms,
        )
        return {
            "matched": result.matched,
            "confidence": result.confidence,
            "score": result.score,
            "beatport_id": result.beatport_id,
            "reasons": list(result.reasons),
            "genre": (result.track or {}).get("genre") if result.track else None,
            "sub_genre": (result.track or {}).get("sub_genre") if result.track else None,
            "bpm": (result.track or {}).get("bpm") if result.track else None,
            "camelot": (result.track or {}).get("camelot") if result.track else None,
            "key": (result.track or {}).get("key") if result.track else None,
            "length_ms": (result.track or {}).get("length_ms") if result.track else None,
            "isrc": (result.track or {}).get("isrc") if result.track else None,
            "release": (result.track or {}).get("release") if result.track else None,
            "label": (result.track or {}).get("label") if result.track else None,
            "track": result.track,
            "candidates_considered": len(candidates),
        }

    # ---------- write (unsupported) ---------- #

    async def write(self, entity: str, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        raise ValidationError("beatport provider is read-only (no write operations)")

    # ---------- search ---------- #

    async def search(self, query: str, type: str = "tracks", limit: int = 10) -> dict[str, Any]:
        raw = await self._client.search(query=query, type=type, per_page=limit)
        tracks = [normalize_track(t) for t in (raw.get("tracks") or [])]
        return {"tracks": tracks, "count": raw.get("count", len(tracks))}

    # ---------- download (subscription-gated) ---------- #

    async def download_audio(self, track_id: str, dest: Path | None = None) -> Path:
        raise SubscriptionRequiredError(
            "Beatport audio download requires a paid Beatport Streaming Professional "
            "subscription; this provider exposes catalog metadata only."
        )

    async def close(self) -> None:
        await self._client.close()
