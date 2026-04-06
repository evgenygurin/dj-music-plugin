"""JSON DJ guide writer."""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.export.models import SetExportData


def write_json_guide(data: SetExportData, output_path: Path) -> Path:
    """Write structured JSON with full set details."""
    guide = {
        "set": {
            "name": data.name,
            "version": data.version_label,
            "quality_score": data.quality_score,
            "track_count": len(data.tracks),
        },
        "tracks": [
            {
                "position": t.position + 1,
                "title": t.title,
                "artist": t.artist,
                "bpm": t.bpm,
                "key": t.key_camelot,
                "energy_lufs": t.energy_lufs,
                "mood": t.mood,
                "duration_ms": t.duration_ms,
                "cue_points": t.cue_points,
                "sections": t.sections,
                **({"audio_features": t.audio_features} if t.audio_features else {}),
            }
            for t in data.tracks
        ],
        "transitions": [
            {
                "from": tr.from_position + 1,
                "to": tr.to_position + 1,
                "score": tr.score,
                "bpm_delta": tr.bpm_delta,
                "key_distance": tr.key_distance,
                "energy_delta": tr.energy_delta,
                "type": tr.transition_type,
                "notes": tr.notes,
            }
            for tr in data.transitions
        ],
        "analytics": {
            "avg_transition_score": (
                sum(t.score or 0 for t in data.transitions) / max(len(data.transitions), 1)
            ),
            "hard_conflicts": sum(
                1 for t in data.transitions if t.score is not None and t.score == 0.0
            ),
            "bpm_range": (
                [
                    min(t.bpm for t in data.tracks if t.bpm),
                    max(t.bpm for t in data.tracks if t.bpm),
                ]
                if any(t.bpm for t in data.tracks)
                else None
            ),
        },
    }

    output_path.write_text(
        json.dumps(guide, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path
