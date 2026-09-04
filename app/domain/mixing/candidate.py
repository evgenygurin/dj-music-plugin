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

    @classmethod
    def from_values(
        cls,
        source: AnalysisSnapshot,
        target: AnalysisSnapshot,
        source_bpm: float,
        target_bpm: float,
        duration_s: float,
    ) -> CandidateTransition:
        st = TempoHypothesis(source_bpm, 1.0, "candidate")
        tt = TempoHypothesis(target_bpm, 1.0, "candidate")
        payload = {
            "source": source.identity_hash,
            "target": target.identity_hash,
            "source_bpm": source_bpm,
            "target_bpm": target_bpm,
            "duration_s": duration_s,
        }
        candidate_id = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return cls(source.identity_hash, target.identity_hash, st, tt, duration_s, candidate_id)


class CandidateGenerator:
    def generate(
        self, source: AnalysisSnapshot, target: AnalysisSnapshot, request: AlignmentRequest
    ) -> tuple[CandidateTransition, ...]:
        candidates: list[CandidateTransition] = []
        for source_h in source.tempo_hypotheses:
            for target_h in target.tempo_hypotheses:
                for target_bpm in target_h.variants():
                    if 20.0 <= target_bpm <= 300.0:
                        candidates.append(
                            CandidateTransition.from_values(
                                source,
                                target,
                                source_h.bpm,
                                target_bpm,
                                request.bars * 4 * 60.0 / source_h.bpm,
                            )
                        )
        return tuple(candidates)
