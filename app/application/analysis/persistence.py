"""Serialization boundary for persisted universal analysis snapshots."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from app.domain.analysis import AnalysisSnapshot

from .normalizers import beatgrid, cues, phrases, sections, tempo_hypotheses


def snapshot_to_payload(snapshot: AnalysisSnapshot) -> dict[str, Any]:
    """Serialize the complete domain analysis payload to JSON-compatible data."""
    return {
        "engine_version": snapshot.engine_version,
        "dsp_backend": snapshot.dsp_backend,
        "analysis_config_hash": snapshot.analysis_config_hash,
        "tempo_hypotheses": [
            {"bpm": item.bpm, "confidence": item.confidence, "source": item.source}
            for item in snapshot.tempo_hypotheses
        ],
        "beatgrid": _beatgrid_payload(snapshot.beatgrid),
        "phrases": [asdict(item) for item in snapshot.phrases],
        "sections": [asdict(item) for item in snapshot.sections],
        "cues": [asdict(item) for item in snapshot.cues],
    }


def snapshot_from_record(record: Mapping[str, Any]) -> AnalysisSnapshot:
    """Rehydrate a snapshot from an ``EngineContractStore`` record."""
    payload = record.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("analysis snapshot payload is invalid")
    return AnalysisSnapshot(
        source_hash=str(record["source_hash"]),
        schema_version=str(record["schema_version"]),
        analyzer_versions=record.get("analyzer_versions", {}),
        engine_version=str(payload.get("engine_version", "universal-1")),
        model_versions=record.get("model_versions", {}),
        dsp_backend=str(payload.get("dsp_backend", "unknown")),
        analysis_config_hash=str(payload.get("analysis_config_hash", "")),
        tempo_hypotheses=tempo_hypotheses(payload.get("tempo_hypotheses", ())),
        beatgrid=beatgrid(payload["beatgrid"]) if payload.get("beatgrid") else None,
        phrases=phrases(payload.get("phrases", ())),
        sections=sections(payload.get("sections", ())),
        cues=cues(payload.get("cues", ())),
    )


def _beatgrid_payload(grid: Any) -> dict[str, Any] | None:
    if grid is None:
        return None
    return {
        "bpm": grid.bpm,
        "beats_per_bar": grid.beats_per_bar,
        "phase_s": grid.phase_s,
        "beats": [
            {"time_s": beat.time_s, "index": beat.index, "is_downbeat": beat.is_downbeat}
            for beat in grid.beats
        ],
    }


def transition_plan_to_payload(plan: Any) -> dict[str, Any]:
    """Serialize an immutable transition plan without losing its identity inputs."""
    return {
        "source_id": plan.source_id,
        "target_id": plan.target_id,
        "duration_bars": plan.duration_bars,
        "effective_bpm": plan.effective_bpm,
        "recipe": {
            "kind": plan.recipe.kind.value,
            "bars": plan.recipe.bars,
            "parameters": list(plan.recipe.parameters),
        },
        "plan_version": plan.plan_version,
        "engine_version": plan.engine_version,
        "config_identity": plan.config_identity,
        "source_analysis_identity": plan.source_analysis_identity,
        "target_analysis_identity": plan.target_analysis_identity,
        "diagnostics": list(plan.diagnostics),
        "execution_identity": plan.execution_identity,
    }
