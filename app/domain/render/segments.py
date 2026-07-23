"""Segment factories for per-mode render-plan segment construction."""

from __future__ import annotations

from typing import Protocol

from app.config.render import RenderSettings
from app.domain.render.models import StemSegment, TrackInput, TrackSegment
from app.domain.render.request import RenderRequest
from app.domain.render.timeline import SegmentGeometry

type RenderSegmentList = list[TrackSegment] | list[StemSegment]


class SegmentFactory(Protocol):
    def build_segments(
        self,
        geometries: list[SegmentGeometry],
        inputs: list[TrackInput],
        stem_paths: dict[int, dict[str, str]] | None,
        settings: RenderSettings,
        request: RenderRequest,
    ) -> RenderSegmentList: ...


class ClassicSegmentFactory:
    def build_segments(
        self,
        geometries: list[SegmentGeometry],
        inputs: list[TrackInput],
        stem_paths: dict[int, dict[str, str]] | None,
        settings: RenderSettings,
        request: RenderRequest,
    ) -> list[TrackSegment]:
        return [
            TrackSegment(
                index=g.index,
                track_id=g.track_id,
                file_path=inputs[g.index].file_path,
                tempo_ratio=g.tempo_ratio,
                trim_start_s=g.trim_start_s,
                gain_db=g.gain_db,
                body_bars=g.body_bars,
                d_in_s=g.d_in_s,
                d_out_s=g.d_out_s,
                length_s=g.length_s,
                start_s=g.start_s,
            )
            for g in geometries
        ]


class StemSegmentFactory:
    def build_segments(
        self,
        geometries: list[SegmentGeometry],
        inputs: list[TrackInput],
        stem_paths: dict[int, dict[str, str]] | None,
        settings: RenderSettings,
        request: RenderRequest,
    ) -> list[StemSegment]:
        stem_paths_by_track = stem_paths or {}
        return [
            StemSegment(
                index=g.index,
                track_idx=g.index,
                track_id=g.track_id,
                stem_paths=stem_paths_by_track.get(g.track_id, {}),
                tempo_ratio=g.tempo_ratio,
                trim_start_s=g.trim_start_s,
                gain_db=g.gain_db,
                body_bars=g.body_bars,
                d_in_s=g.d_in_s,
                d_out_s=g.d_out_s,
                length_s=g.length_s,
                start_s=g.start_s,
                target_bpm=settings.target_bpm,
                low_swap_beats=settings.low_swap_beats,
                eq_phase_1_ratio=settings.eq_phase_1_ratio,
                eq_phase_2_ratio=settings.eq_phase_2_ratio,
            )
            for g in geometries
        ]
