"""Import & download service — import YM tracks, download MP3, link to library.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.errors import ValidationError
from app.models.library import DjLibraryItem
from app.models.track import Track
from app.repositories.ingestion import IngestionRepository
from app.repositories.track import TrackRepository
from app.ym.client import YandexMusicClient


def _sanitize_filename(title: str, max_len: int = 80) -> str:
    """Sanitize string for safe filename."""
    safe = re.sub(r'[/\\:*?"<>|]', "", title)
    safe = safe.replace(" ", "_")
    safe = re.sub(r"_+", "_", safe).strip("_")[:max_len]
    return safe or "untitled"


class ImportService:
    """Import and download tracks from YM."""

    def __init__(
        self,
        track_repo: TrackRepository,
        ym: YandexMusicClient,
        metadata_service: Any | None = None,
        ingestion_repo: IngestionRepository | None = None,
    ) -> None:
        self._tracks = track_repo
        self._ym = ym
        self._metadata = metadata_service
        self._ingestion = ingestion_repo

    async def import_tracks(
        self,
        track_refs: list[str],
    ) -> dict[str, Any]:
        """Import YM track IDs into local DB. Idempotent — skips existing."""
        if not track_refs:
            raise ValidationError("track_refs is required (list of YM track IDs)")

        imported = 0
        skipped = 0
        imported_ids: list[str] = []
        id_mapping: dict[str, int] = {}

        for ref in track_refs:
            ym_id = str(ref).strip()
            if not ym_id:
                continue

            existing = await self._tracks.get_by_external_id("yandex_music", ym_id)
            if existing is not None:
                skipped += 1
                continue

            track = await self._tracks.create(Track(title=f"YM:{ym_id}", status=0))
            await self._tracks.add_external_id(track.id, "yandex_music", ym_id)
            imported += 1
            imported_ids.append(ym_id)
            id_mapping[ym_id] = track.id

        # Enrich with YM metadata (batch fetch)
        enriched = await self._enrich_from_ym(imported_ids, id_mapping)

        return {
            "imported": imported,
            "skipped": skipped,
            "enriched": enriched,
            "total_refs": len(track_refs),
        }

    async def download_tracks(
        self,
        track_refs: list[str],
        target_dir: str | None = None,
        skip_existing: bool = True,
        prefer_bitrate: int = 320,
    ) -> dict[str, Any]:
        """Download MP3 from YM and link to library."""
        if not track_refs:
            raise ValidationError("track_refs is required (list of YM track IDs)")

        dest_dir = Path(target_dir or settings.ym_library_path or "~/Music/DJ/").expanduser()
        dest_dir.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        skipped_count = 0
        linked = 0
        failed = 0
        errors: list[dict[str, str]] = []
        files: list[dict[str, Any]] = []

        for ref in track_refs:
            ym_id = str(ref).strip()
            if not ym_id:
                continue

            filename = await self._resolve_filename(ym_id)
            dest_path = dest_dir / filename

            # Skip existing files (but still link to library)
            if skip_existing and dest_path.exists() and dest_path.stat().st_size > 1000:
                skipped_count += 1
                files.append({"ym_id": ym_id, "path": str(dest_path), "status": "skipped"})
                linked += await self._link_file_to_track(ym_id, dest_path)
                continue

            try:
                file_size = await self._ym.download_track(
                    ym_id,
                    str(dest_path),
                    prefer_bitrate=prefer_bitrate,
                )
                downloaded += 1
                files.append(
                    {
                        "ym_id": ym_id,
                        "path": str(dest_path),
                        "size_bytes": file_size,
                        "status": "downloaded",
                    }
                )
                linked += await self._link_file_to_track(ym_id, dest_path)
            except Exception as e:
                failed += 1
                errors.append({"ym_id": ym_id, "error": str(e)[:100]})

        return {
            "requested": len(track_refs),
            "downloaded": downloaded,
            "skipped": skipped_count,
            "linked_to_library": linked,
            "failed": failed,
            "target_dir": str(dest_dir),
            "files": files[:20],
            "errors": errors[:10] if errors else [],
        }

    # ── Private ──────────────────────────────────────

    async def _resolve_filename(self, ym_id: str) -> str:
        """Resolve a human-readable filename from YM metadata."""
        try:
            ym_tracks = await self._ym.get_tracks([ym_id])
            if ym_tracks:
                t = ym_tracks[0]
                artists = ", ".join(str(a.get("name", "?")) for a in (t.artists or []))
                return f"{_sanitize_filename(artists)} - {_sanitize_filename(t.title)}.mp3"
        except Exception:
            pass
        return f"ym_{ym_id}.mp3"

    async def _enrich_from_ym(
        self,
        imported_ids: list[str],
        id_mapping: dict[str, int],
    ) -> int:
        """Enrich imported tracks with YM metadata. Returns count of enriched."""
        if not imported_ids:
            return 0

        enriched = 0
        try:
            ym_tracks = await self._ym.get_tracks(imported_ids)
            ym_by_id = {str(t.id): t for t in ym_tracks}

            for ym_id_str, local_track_id in id_mapping.items():
                ym_track = ym_by_id.get(ym_id_str)
                if not ym_track:
                    continue

                # Cache raw provider response
                await self._cache_ym_response(local_track_id, ym_track)

                local_track = await self._tracks.get_by_id(local_track_id)
                if local_track and local_track.title.startswith("YM:"):
                    artists = ", ".join(a.get("name", "?") for a in (ym_track.artists or []))
                    local_track.title = (
                        f"{artists} - {ym_track.title}" if artists else ym_track.title
                    )
                    if ym_track.duration_ms:
                        local_track.duration_ms = ym_track.duration_ms
                    await self._tracks.update(local_track)

                await self._tracks.save_ym_metadata(
                    track_id=local_track_id,
                    ym_id=ym_id_str,
                    ym_track=ym_track,
                )

                # Normalize metadata into Artist/Genre/Label/Release entities
                if self._metadata is not None:
                    with contextlib.suppress(Exception):
                        await self._metadata.normalize_track_metadata(
                            local_track_id, ym_track=ym_track
                        )

                enriched += 1
        except Exception:
            pass  # YM metadata enrichment is best-effort

        return enriched

    async def _cache_ym_response(
        self,
        track_id: int,
        ym_track: Any,
    ) -> None:
        """Cache YM track metadata as raw provider response."""
        if self._ingestion is None:
            return
        try:
            raw_data = (
                ym_track.model_dump()
                if hasattr(ym_track, "model_dump")
                else {
                    "id": ym_track.id,
                    "title": ym_track.title,
                    "duration_ms": ym_track.duration_ms,
                    "artists": ym_track.artists,
                    "albums": ym_track.albums,
                    "cover_uri": ym_track.cover_uri,
                    "explicit": ym_track.explicit,
                }
            )
            await self._ingestion.cache_response(
                track_id=track_id,
                provider_name="yandex_music",
                raw_data=raw_data,
            )
        except Exception:
            pass  # Caching is best-effort

    async def _link_file_to_track(
        self,
        ym_id: str,
        file_path: Path,
    ) -> int:
        """Find local track by YM ID, create DjLibraryItem if missing.

        Returns 1 if linked, 0 if not (no track found or already linked).
        """
        ext = await self._tracks.get_by_external_id("yandex_music", ym_id)
        if ext is None:
            return 0

        track_id = ext if isinstance(ext, int) else ext.track_id

        existing = await self._tracks.get_library_item(track_id)
        if existing is not None:
            return 0

        file_hash = hashlib.md5(file_path.read_bytes()).hexdigest()

        item = DjLibraryItem(
            track_id=track_id,
            file_path=str(file_path),
            file_hash=file_hash,
            file_size=file_path.stat().st_size,
            mime_type="audio/mpeg",
            source_app="ym_download",
        )
        await self._tracks.save_library_item(item)
        return 1
