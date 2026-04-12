"""DJ library domain schemas — file items, beatgrids, cue points."""

from __future__ import annotations

from dj_music.schemas.base import BaseEntity


class LibraryItem(BaseEntity):
    """A physical audio file in the DJ library."""

    track_id: int = 0
    file_path: str = ""
    file_hash: str = ""
    file_size: int = 0
    mime_type: str | None = None
    bitrate: int | None = None
    sample_rate: int | None = None
    channels: int | None = None
    source_app: str | None = None


class Beatgrid(BaseEntity):
    """BPM grid for a track."""

    library_item_id: int = 0
    bpm: float = 0.0
    first_downbeat_ms: float | None = None
    grid_offset_ms: float | None = None
    confidence: float | None = None
    variable_tempo: bool = False
    canonical: bool = False


class CuePoint(BaseEntity):
    """A named position in a track."""

    library_item_id: int = 0
    position_ms: float = 0.0
    kind: int = 0  # CueKind int value
    hotcue_index: int | None = None
    label: str | None = None
    color: str | None = None
    # TODO: add quantized, source_app during Phase 4
