"""Set Narrative Engine — Claude reasons about set "story".

Provides structured analysis of a set's narrative arc:
intro → tension → release → peak → cooldown.
Used by Claude Code to explain WHY a set works and suggest improvements.
"""

from __future__ import annotations

from typing import Any, TypedDict


class _PhaseEntry(TypedDict):
    phase: str
    start: float
    end: float
    description: str


# Narrative phases mapped from set position (0.0-1.0)
NARRATIVE_PHASES: list[_PhaseEntry] = [
    {
        "phase": "opening",
        "start": 0.0,
        "end": 0.15,
        "description": "Set the mood, establish BPM and key center",
    },
    {
        "phase": "building",
        "start": 0.15,
        "end": 0.35,
        "description": "Gradually increase energy, introduce complexity",
    },
    {
        "phase": "tension",
        "start": 0.35,
        "end": 0.50,
        "description": "Push toward peak, darker or more driving sounds",
    },
    {
        "phase": "peak",
        "start": 0.50,
        "end": 0.70,
        "description": "Maximum energy, hardest tracks, crowd at full",
    },
    {
        "phase": "release",
        "start": 0.70,
        "end": 0.85,
        "description": "Begin cooldown, lighter textures, breakdowns",
    },
    {
        "phase": "closing",
        "start": 0.85,
        "end": 1.0,
        "description": "Wind down, return to ambient or melodic",
    },
]


class SetNarrativeEngine:
    """Analyzes and scores set narrative quality."""

    def analyze_narrative(
        self,
        tracks: list[dict[str, Any]],
        template_name: str | None = None,
    ) -> dict[str, Any]:
        """Analyze a set's narrative structure.

        Args:
            tracks: List of {position: 0-1, bpm, energy_lufs, mood, title}
            template_name: Optional template to compare against

        Returns:
            Narrative analysis with phase scores, flow quality, suggestions.
        """
        if not tracks:
            return {"error": "empty set"}

        total = len(tracks)
        phases: list[dict[str, Any]] = []

        for phase_def in NARRATIVE_PHASES:
            start_idx = int(float(phase_def["start"]) * total)
            end_idx = max(start_idx + 1, int(float(phase_def["end"]) * total))
            phase_tracks = tracks[start_idx:end_idx]

            if not phase_tracks:
                continue

            bpms: list[float] = [float(t["bpm"]) for t in phase_tracks if t.get("bpm") is not None]
            moods: list[str] = [str(t["mood"]) for t in phase_tracks if t.get("mood") is not None]
            energies: list[float] = [
                float(t["energy_lufs"]) for t in phase_tracks if t.get("energy_lufs") is not None
            ]

            avg_bpm = sum(bpms) / len(bpms) if bpms else None
            avg_energy = sum(energies) / len(energies) if energies else None
            mood_variety = len(set(moods))
            dominant_mood = max(set(moods), key=moods.count) if moods else None

            phases.append(
                {
                    "phase": phase_def["phase"],
                    "description": phase_def["description"],
                    "track_count": len(phase_tracks),
                    "avg_bpm": round(avg_bpm, 1) if avg_bpm else None,
                    "avg_energy": round(avg_energy, 1) if avg_energy else None,
                    "dominant_mood": dominant_mood,
                    "mood_variety": mood_variety,
                    "tracks": [t.get("title", "?") for t in phase_tracks[:3]],
                }
            )

        # Score narrative quality
        flow_score = self._score_flow(phases)
        variety_score = self._score_variety(tracks)
        arc_score = self._score_arc(phases)

        suggestions = self._generate_suggestions(phases, flow_score, arc_score)

        return {
            "phases": phases,
            "scores": {
                "flow": round(flow_score, 2),
                "variety": round(variety_score, 2),
                "arc": round(arc_score, 2),
                "overall": round((flow_score + variety_score + arc_score) / 3, 2),
            },
            "suggestions": suggestions,
            "track_count": total,
        }

    def _score_flow(self, phases: list[dict[str, Any]]) -> float:
        """Score BPM flow smoothness (0-1)."""
        bpms: list[float] = [float(p["avg_bpm"]) for p in phases if p["avg_bpm"] is not None]
        if len(bpms) < 2:
            return 0.5
        jumps = [abs(bpms[i + 1] - bpms[i]) for i in range(len(bpms) - 1)]
        avg_jump = sum(jumps) / len(jumps)
        return float(max(0, 1.0 - avg_jump / 10))  # 10 BPM jump = 0 score

    def _score_variety(self, tracks: list[dict[str, Any]]) -> float:
        """Score mood variety (0-1)."""
        moods = [t.get("mood") for t in tracks if t.get("mood")]
        if not moods:
            return 0.5
        unique = len(set(moods))
        return min(1.0, unique / 5)  # 5+ unique moods = perfect

    def _score_arc(self, phases: list[dict[str, Any]]) -> float:
        """Score energy arc shape (0-1). Peak should be in middle."""
        energies = [p["avg_energy"] for p in phases if p["avg_energy"] is not None]
        if len(energies) < 3:
            return 0.5
        peak_idx = energies.index(max(energies))
        ideal_peak = len(energies) * 0.6  # 60% through
        distance = abs(peak_idx - ideal_peak) / len(energies)
        return max(0, 1.0 - distance * 2)

    def _generate_suggestions(
        self, phases: list[dict[str, Any]], flow: float, arc: float
    ) -> list[str]:
        suggestions = []
        if flow < 0.5:
            suggestions.append(
                "BPM jumps too large between phases — consider smoother transitions"
            )
        if arc < 0.5:
            suggestions.append(
                "Energy peak not centered — move highest energy tracks to 50-70% of set"
            )

        # Check opening
        opening = next((p for p in phases if p["phase"] == "opening"), None)
        if opening and opening.get("dominant_mood") in ("industrial", "hard_techno", "peak_time"):
            suggestions.append(
                "Opening is too aggressive — start with ambient_dub, dub_techno, or minimal"
            )

        # Check closing
        closing = next((p for p in phases if p["phase"] == "closing"), None)
        if closing and closing.get("dominant_mood") in ("industrial", "hard_techno", "peak_time"):
            suggestions.append(
                "Closing is too intense — end with melodic_deep, progressive, or ambient_dub"
            )

        if not suggestions:
            suggestions.append("Set narrative looks solid — good energy arc and flow")

        return suggestions
