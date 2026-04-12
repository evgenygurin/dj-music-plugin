"""Search service — cross-entity text search and parametric filtering.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from typing import Any

from dj_music.core.camelot import camelot_to_key_code, is_compatible, key_code_to_camelot
from dj_music.core.constants import KEY_CODE_MAX, KEY_CODE_MIN
from dj_music.core.errors import ValidationError
from dj_music.core.utils.pagination import CursorPage
from dj_music.models.track import Track
from dj_music.repositories.feature import FeatureRepository
from dj_music.repositories.playlist import PlaylistRepository
from dj_music.repositories.set import SetRepository
from dj_music.repositories.track import TrackRepository


class SearchService:
    """Cross-entity search and parametric track filtering."""

    def __init__(
        self,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        set_repo: SetRepository,
        feature_repo: FeatureRepository,
    ) -> None:
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._sets = set_repo
        self._features = feature_repo

    async def search(
        self,
        query: str,
        entity: str = "all",
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search across tracks, artists, playlists, and sets."""
        if not query or not query.strip():
            raise ValidationError("Query must not be empty")

        results: dict[str, list[dict[str, Any]]] = {}
        entities = [entity] if entity != "all" else ["tracks", "artists", "playlists", "sets"]

        if "tracks" in entities:
            tracks = await self._tracks.search_by_text(query.strip(), limit=limit)
            track_ids = [t.id for t in tracks]
            artist_map = await self._tracks.get_artist_names_batch(track_ids) if track_ids else {}
            features_map = await self._features.get_features_batch(track_ids) if track_ids else {}
            track_results: list[dict[str, Any]] = []
            for t in tracks:
                feat = features_map.get(t.id)
                track_results.append(
                    {
                        "id": t.id,
                        "title": t.title,
                        "artist_names": artist_map.get(t.id, []),
                        "bpm": feat.bpm if feat else None,
                        "key_camelot": (
                            key_code_to_camelot(feat.key_code)
                            if feat and feat.key_code is not None
                            else None
                        ),
                        "duration_ms": t.duration_ms,
                    }
                )
            results["tracks"] = track_results

        if "artists" in entities:
            artists = await self._tracks.search_artists(query.strip(), limit=limit)
            results["artists"] = [{"id": a.id, "name": a.name} for a in artists]

        if "playlists" in entities:
            playlists = await self._playlists.search_by_name(query.strip(), limit=limit)
            results["playlists"] = [{"id": p.id, "name": p.name} for p in playlists]

        if "sets" in entities:
            sets = await self._sets.search_by_name_list(query.strip(), limit=limit)
            results["sets"] = [{"id": s.id, "name": s.name} for s in sets]

        total = sum(len(v) for v in results.values())
        return {"query": query, "total": total, "results": results}

    async def filter_tracks(
        self,
        *,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        key: str | None = None,
        key_compatible: str | None = None,
        energy_min: float | None = None,
        energy_max: float | None = None,
        has_features: bool | None = None,
        exclude_set_id: int | None = None,
        sort_by: str = "bpm",
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[Track]:
        """Filter tracks by audio features with parametric queries."""
        key_code: int | None = None
        compatible_codes: list[int] | None = None

        if key is not None:
            try:
                key_code = camelot_to_key_code(key.upper())
            except ValueError as err:
                raise ValidationError(f"Invalid Camelot key: {key!r}") from err

        if key_compatible is not None:
            compatible_codes = self._compatible_key_codes(key_compatible)
            if not compatible_codes:
                raise ValidationError(f"Invalid Camelot key: {key_compatible!r}")

        return await self._tracks.filter_tracks_advanced(
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            key_code=key_code,
            compatible_key_codes=compatible_codes,
            energy_min=energy_min,
            energy_max=energy_max,
            has_features=has_features,
            exclude_set_id=exclude_set_id,
            sort_by=sort_by,
            limit=limit,
            cursor=cursor,
        )

    @staticmethod
    def _compatible_key_codes(notation: str) -> list[int]:
        """Return all key_codes compatible with the given Camelot notation."""
        try:
            base_code = camelot_to_key_code(notation.upper())
        except ValueError:
            return []
        return [
            code
            for code in range(KEY_CODE_MIN, KEY_CODE_MAX + 1)
            if is_compatible(base_code, code)
        ]
