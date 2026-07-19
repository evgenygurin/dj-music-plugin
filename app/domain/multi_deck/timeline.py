"""Unified timeline overlay for multi-deck synchronization."""

from __future__ import annotations

from typing import Any

from app.repositories.unit_of_work import UnitOfWork


async def build_timeline_overlay(
    uow: UnitOfWork,
    track_ids: list[int],
    align_mode: str = "downbeat",
) -> dict[str, Any]:
    tracks = []

    for tid in track_ids:
        sections = await uow.track_features.get_track_sections(tid)
        beatgrids = await uow.audio_files.get_beatgrids(tid)
        first_downbeat_ms: float = 0.0
        for bg in beatgrids or []:
            downbeat = getattr(bg, "first_downbeat_ms", None)
            if getattr(bg, "canonical", False) and downbeat is not None:
                first_downbeat_ms = float(downbeat)
                break

        bpm = None
        features_row = await uow.track_features.get_by_track_id(tid)
        if features_row and features_row.bpm is not None:
            bpm = features_row.bpm

        tracks.append(
            {
                "track_id": tid,
                "first_downbeat_ms": first_downbeat_ms,
                "bpm": bpm,
                "sections": sections,
            }
        )

    return {
        "tracks": tracks,
        "description": "Aligned by first downbeat. Use start_ms + offset for sync.",
    }
