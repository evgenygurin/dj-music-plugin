"""Cheap, deterministic transition candidate generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.domain.analysis.snapshot import AnalysisSnapshot
from app.domain.analysis.tempo import TempoHypothesis

from .alignment import AlignmentRequest


@dataclass(frozen=True, slots=True)
class CandidateTransition:
    source_hash: str
    target_hash: str
    source_tempo: TempoHypothesis
    target_tempo: TempoHypothesis
    duration_s: float
    candidate_id: str
    source_variant: str = "1x"
    target_variant: str = "1x"
    phase_offset_s: float = 0.0
    downbeat_offset_beats: float = 0.0
    phrase_offset_bars: int = 0

    @classmethod
    def from_values(
        cls,
        source: AnalysisSnapshot,
        target: AnalysisSnapshot,
        source_bpm: float,
        target_bpm: float,
        duration_s: float,
        *,
        source_variant: str = "1x",
        target_variant: str = "1x",
        phase_offset_s: float = 0.0,
        downbeat_offset_beats: float = 0.0,
        phrase_offset_bars: int = 0,
    ) -> CandidateTransition:
        st = TempoHypothesis(source_bpm, 1.0, "candidate")
        tt = TempoHypothesis(target_bpm, 1.0, "candidate")
        payload = {
            "source": source.identity_hash,
            "target": target.identity_hash,
            "source_bpm": source_bpm,
            "target_bpm": target_bpm,
            "duration_s": duration_s,
            "source_variant": source_variant,
            "target_variant": target_variant,
            "phase_offset_s": phase_offset_s,
            "downbeat_offset_beats": downbeat_offset_beats,
            "phrase_offset_bars": phrase_offset_bars,
        }
        candidate_id = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return cls(
            source.identity_hash,
            target.identity_hash,
            st,
            tt,
            duration_s,
            candidate_id,
            source_variant,
            target_variant,
            phase_offset_s,
            downbeat_offset_beats,
            phrase_offset_bars,
        )


class CandidateGenerator:
    def generate(
        self, source: AnalysisSnapshot, target: AnalysisSnapshot, request: AlignmentRequest
    ) -> tuple[CandidateTransition, ...]:
        candidates: list[CandidateTransition] = []
        phase_offset_s = 0.0
        if source.beatgrid is not None and target.beatgrid is not None:
            phase_offset_s = target.beatgrid.phase_s - source.beatgrid.phase_s
        phrase_offset_bars = 0
        if source.phrases and target.phrases:
            phrase_offset_bars = target.phrases[0].start_bar - source.phrases[0].start_bar
        for source_h in source.tempo_hypotheses:
            for target_h in target.tempo_hypotheses:
                for source_bpm in source_h.variants():
                    for target_bpm in target_h.variants():
                        if 20.0 <= target_bpm <= 300.0 and 20.0 <= source_bpm <= 300.0:
                            target_period = 60.0 / target_bpm
                            candidates.append(
                                CandidateTransition.from_values(
                                    source,
                                    target,
                                    source_bpm,
                                    target_bpm,
                                    request.bars * 4 * 60.0 / source_bpm,
                                    source_variant=f"{source_bpm / source_h.bpm:g}x",
                                    target_variant=f"{target_bpm / target_h.bpm:g}x",
                                    phase_offset_s=phase_offset_s,
                                    downbeat_offset_beats=phase_offset_s / target_period,
                                    phrase_offset_bars=phrase_offset_bars,
                                )
                            )
        return tuple(candidates)
