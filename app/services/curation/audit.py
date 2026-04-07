"""Playlist audit sub-service."""

from __future__ import annotations

from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.domain.audit.rules import DEFAULT_AUDIT_RULES, run_audit_rules
from app.repositories.feature import FeatureRepository
from app.repositories.playlist import PlaylistRepository
from app.repositories.track import TrackRepository


class PlaylistAuditService:
    """Audit playlists for techno quality criteria and gaps."""

    def __init__(
        self,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        feature_repo: FeatureRepository,
    ) -> None:
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._features = feature_repo

    async def audit_playlist(
        self,
        playlist_id: int | None = None,
        playlist_query: str | None = None,
    ) -> dict[str, Any]:
        """Audit playlist for techno quality criteria and gaps."""
        if playlist_id is None and playlist_query is None:
            raise ValidationError("Provide playlist_id or playlist_query")

        playlist = None
        if playlist_id is not None:
            playlist = await self._playlists.get_with_items(playlist_id)
        elif playlist_query:
            playlist = await self._playlists.search_with_items(playlist_query)

        if playlist is None:
            raise NotFoundError("Playlist", playlist_id or playlist_query)

        track_ids = [item.track_id for item in sorted(playlist.items, key=lambda i: i.sort_index)]
        if not track_ids:
            raise ValidationError("Playlist is empty")

        issues: list[dict[str, Any]] = []
        stats: dict[str, Any] = {
            "total_tracks": len(track_ids),
            "with_features": 0,
            "without_features": 0,
        }
        bpm_values: list[float] = []
        energy_values: list[float] = []

        # Batch-load tracks and features in two queries instead of 2N
        tracks_map = await self._tracks.get_by_ids(track_ids)
        features_map = await self._features.get_features_batch(track_ids)

        for tid in track_ids:
            track = tracks_map.get(tid)
            if track is None:
                issues.append({"track_id": tid, "issue": "track_missing", "severity": "error"})
                continue

            features = features_map.get(tid)
            if features is None:
                stats["without_features"] += 1
                issues.append(
                    {
                        "track_id": tid,
                        "title": track.title,
                        "issue": "no_audio_features",
                        "severity": "warning",
                    }
                )
                continue

            stats["with_features"] += 1

            if features.bpm is not None:
                bpm_values.append(features.bpm)
            if features.integrated_lufs is not None:
                energy_values.append(features.integrated_lufs)

            # Run all audit rules via Chain of Responsibility
            audit_issues = run_audit_rules(DEFAULT_AUDIT_RULES, tid, track.title, features)
            for ai in audit_issues:
                issue_dict: dict[str, Any] = {
                    "track_id": ai.track_id,
                    "title": ai.title,
                    "issue": ai.issue,
                    "severity": ai.severity,
                }
                if ai.detail is not None:
                    issue_dict["detail"] = ai.detail
                issues.append(issue_dict)

        if bpm_values:
            stats["bpm_range"] = [round(min(bpm_values), 1), round(max(bpm_values), 1)]
            stats["bpm_mean"] = round(sum(bpm_values) / len(bpm_values), 1)
        if energy_values:
            stats["lufs_range"] = [round(min(energy_values), 1), round(max(energy_values), 1)]
            stats["lufs_mean"] = round(sum(energy_values) / len(energy_values), 1)

        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]

        return {
            "playlist_id": playlist.id,
            "playlist_name": playlist.name,
            "stats": stats,
            "errors": len(errors),
            "warnings": len(warnings),
            "issues": issues,
        }
