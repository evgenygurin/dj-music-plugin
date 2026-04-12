"""DJ Set domain schemas."""

from __future__ import annotations

from pydantic import BaseModel

from dj_music.schemas.base import BaseEntity


class SetSummary(BaseModel):
    """Compact DJ set projection for list views."""

    id: int
    name: str
    track_count: int = 0
    template: str | None = None
    latest_score: float | None = None


class DjSet(BaseEntity):
    """A planned DJ performance."""

    name: str = ""
    description: str | None = None
    target_duration_ms: int | None = None
    target_bpm_min: float | None = None
    target_bpm_max: float | None = None
    template_name: str | None = None
    source_playlist_id: int | None = None
    ym_playlist_id: str | None = None


class SetVersion(BaseEntity):
    """A snapshot of a set's track ordering."""

    set_id: int = 0
    label: str | None = None
    quality_score: float | None = None
    # TODO: add generator_run_meta during Phase 4


class SetItem(BaseEntity):
    """A track in a set version."""

    version_id: int = 0
    track_id: int = 0
    sort_index: int = 0
    mix_in_point_ms: int | None = None
    mix_out_point_ms: int | None = None
    notes: str | None = None
    pinned: bool = False
    # TODO: add transition_id, out/in_section_id, planned_eq during Phase 4
