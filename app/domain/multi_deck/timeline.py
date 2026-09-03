"""Unified timeline overlay for multi-deck synchronization."""

from __future__ import annotations

from typing import Any, Protocol


class TimelineDataReader(Protocol):
    """Port for loading timeline data; infrastructure implements this protocol."""

    async def get_track_sections(self, track_id: int) -> list[dict[str, Any]]: ...
    async def get_beatgrids(self, track_id: int) -> list[object]: ...
    async def get_by_track_id(self, track_id: int) -> object | None: ...


async def build_timeline_overlay(
    data_reader: TimelineDataReader,
    track_ids: list[int],
    align_mode: str = "downbeat",
) -> dict[str, Any]:
    """Build a timeline from repository data supplied through an abstract port."""
    tracks = []
    for tid in track_ids:
        sections = await data_reader.get_track_sections(tid)
        beatgrids = await data_reader.get_beatgrids(tid)
        first_downbeat_ms = 0.0
        for bg in beatgrids or []:
            downbeat = getattr(bg, "first_downbeat_ms", None)
            if getattr(bg, "canonical", False) and downbeat is not None:
                first_downbeat_ms = float(downbeat)
                break

        features_row = await data_reader.get_by_track_id(tid)
        bpm = getattr(features_row, "bpm", None) if features_row else None
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
