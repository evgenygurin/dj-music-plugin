"""Shared color palette for Prefab UI tools.

Single source of truth for subgenre, Camelot wheel, and energy-level
colors used by the Prefab UI tools rendered inside MCP clients
(Claude Desktop / Claude Code).
"""

from __future__ import annotations

# ── Subgenre palette (15 techno subgenres, ordered by energy) ──────────
SUBGENRE_COLORS: dict[str, str] = {
    "ambient_dub": "#6366f1",
    "dub_techno": "#818cf8",
    "minimal": "#a5b4fc",
    "detroit": "#60a5fa",
    "melodic_deep": "#38bdf8",
    "progressive": "#2dd4bf",
    "hypnotic": "#34d399",
    "driving": "#a3e635",
    "tribal": "#facc15",
    "breakbeat": "#fb923c",
    "peak_time": "#f97316",
    "acid": "#f43f5e",
    "raw": "#e11d48",
    "industrial": "#dc2626",
    "hard_techno": "#991b1b",
}

SUBGENRE_LABELS: dict[str, str] = {
    "ambient_dub": "Ambient Dub",
    "dub_techno": "Dub Techno",
    "minimal": "Minimal",
    "detroit": "Detroit",
    "melodic_deep": "Melodic Deep",
    "progressive": "Progressive",
    "hypnotic": "Hypnotic",
    "driving": "Driving",
    "tribal": "Tribal",
    "breakbeat": "Breakbeat",
    "peak_time": "Peak Time",
    "acid": "Acid",
    "raw": "Raw",
    "industrial": "Industrial",
    "hard_techno": "Hard Techno",
}

# Mood == subgenre in this project.
MOOD_COLORS: dict[str, str] = dict(SUBGENRE_COLORS)
MOOD_LABELS: dict[str, str] = dict(SUBGENRE_LABELS)

# ── Energy level palette (1..10 discrete buckets) ──────────────────────
# Cyan → green → amber → red ramp, matches cyberpunk dashboard theme.
ENERGY_LEVEL_COLORS: dict[int, str] = {
    1: "#0ea5e9",
    2: "#06b6d4",
    3: "#14b8a6",
    4: "#22c55e",
    5: "#84cc16",
    6: "#eab308",
    7: "#f59e0b",
    8: "#f97316",
    9: "#ef4444",
    10: "#dc2626",
}

# ── Camelot wheel (24 slots) ──────────────────────────────────────────
# Minor keys ("A"): blue/purple gradient around the wheel.
# Major keys ("B"): warm magenta/orange gradient.
CAMELOT_WHEEL_COLORS: dict[str, str] = {
    "1A": "#1e40af",
    "2A": "#1d4ed8",
    "3A": "#2563eb",
    "4A": "#3b82f6",
    "5A": "#4f46e5",
    "6A": "#6366f1",
    "7A": "#7c3aed",
    "8A": "#8b5cf6",
    "9A": "#a855f7",
    "10A": "#9333ea",
    "11A": "#7e22ce",
    "12A": "#6b21a8",
    "1B": "#be185d",
    "2B": "#db2777",
    "3B": "#e11d48",
    "4B": "#ef4444",
    "5B": "#f97316",
    "6B": "#f59e0b",
    "7B": "#eab308",
    "8B": "#facc15",
    "9B": "#d97706",
    "10B": "#c2410c",
    "11B": "#b91c1c",
    "12B": "#9f1239",
}

# ── Score badges (pass / warn / fail) ─────────────────────────────────
PASS_COLOR = "#22c55e"
WARN_COLOR = "#f59e0b"
FAIL_COLOR = "#ef4444"
NEUTRAL_COLOR = "#64748b"


def energy_color(level: int) -> str:
    """Clamp a 1..10 energy integer to the palette; fallback to neutral."""
    if 1 <= level <= 10:
        return ENERGY_LEVEL_COLORS[level]
    return NEUTRAL_COLOR


def score_color(score: float) -> str:
    """Map a 0..1 transition score to pass/warn/fail."""
    if score >= 0.75:
        return PASS_COLOR
    if score >= 0.5:
        return WARN_COLOR
    return FAIL_COLOR
