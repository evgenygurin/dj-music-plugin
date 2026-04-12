"""Template registry — 8 pre-defined DJ set energy arc templates."""

from __future__ import annotations

from dj_music.templates.models import SetTemplateDefinition, TemplateSlot

TEMPLATES: dict[str, SetTemplateDefinition] = {
    # ── 1. Warm-up opener (30 min) ─────────────────────
    "warm_up_30": SetTemplateDefinition(
        name="warm_up_30",
        duration_min=30,
        description="Low-energy opener, gradual introduction",
        slots=(
            TemplateSlot(0.00, "ambient_dub", -14.0, 120, 126, 180_000, 0.8),
            TemplateSlot(0.25, "dub_techno", -12.0, 122, 128, 180_000, 0.7),
            TemplateSlot(0.50, "minimal", -10.0, 124, 130, 180_000, 0.6),
            TemplateSlot(0.75, "melodic_deep", -9.0, 126, 132, 180_000, 0.5),
        ),
    ),
    # ── 2. Classic set (60 min) ────────────────────────
    "classic_60": SetTemplateDefinition(
        name="classic_60",
        duration_min=60,
        description="Standard build-peak-release arc",
        slots=(
            TemplateSlot(0.00, "minimal", -12.0, 124, 130, 180_000, 0.7),
            TemplateSlot(0.10, "dub_techno", -11.0, 126, 132, 180_000, 0.6),
            TemplateSlot(0.20, "melodic_deep", -10.0, 128, 134, 180_000, 0.5),
            TemplateSlot(0.35, "progressive", -9.0, 130, 136, 180_000, 0.5),
            TemplateSlot(0.50, "driving", -8.0, 132, 138, 180_000, 0.4),
            TemplateSlot(0.65, "peak_time", -7.0, 134, 140, 180_000, 0.3),
            TemplateSlot(0.80, "hypnotic", -8.0, 132, 138, 180_000, 0.5),
            TemplateSlot(0.90, "melodic_deep", -10.0, 128, 134, 180_000, 0.6),
        ),
    ),
    # ── 3. Peak hour (60 min) ──────────────────────────
    "peak_hour_60": SetTemplateDefinition(
        name="peak_hour_60",
        duration_min=60,
        description="High-energy throughout, relentless intensity",
        slots=(
            TemplateSlot(0.00, "driving", -8.0, 134, 140, 180_000, 0.4),
            TemplateSlot(0.15, "peak_time", -7.0, 136, 142, 180_000, 0.3),
            TemplateSlot(0.30, "acid", -6.5, 138, 144, 180_000, 0.3),
            TemplateSlot(0.45, "raw", -6.0, 140, 146, 180_000, 0.3),
            TemplateSlot(0.60, "industrial", -5.5, 140, 148, 180_000, 0.3),
            TemplateSlot(0.75, "peak_time", -6.0, 138, 144, 180_000, 0.3),
            TemplateSlot(0.90, "driving", -7.0, 136, 142, 180_000, 0.4),
        ),
    ),
    # ── 4. Roller (90 min) ─────────────────────────────
    "roller_90": SetTemplateDefinition(
        name="roller_90",
        duration_min=90,
        description="Sustained driving energy, hypnotic flow",
        slots=(
            TemplateSlot(0.00, "minimal", -10.0, 130, 136, 180_000, 0.5),
            TemplateSlot(0.12, "hypnotic", -9.0, 132, 138, 180_000, 0.4),
            TemplateSlot(0.25, "driving", -8.0, 134, 140, 180_000, 0.3),
            TemplateSlot(0.37, "tribal", -7.5, 134, 140, 180_000, 0.4),
            TemplateSlot(0.50, "driving", -7.0, 136, 142, 180_000, 0.3),
            TemplateSlot(0.62, "hypnotic", -7.5, 134, 140, 180_000, 0.4),
            TemplateSlot(0.75, "driving", -7.0, 136, 142, 180_000, 0.3),
            TemplateSlot(0.87, "hypnotic", -8.0, 132, 138, 180_000, 0.4),
        ),
    ),
    # ── 5. Progressive (120 min) ───────────────────────
    "progressive_120": SetTemplateDefinition(
        name="progressive_120",
        duration_min=120,
        description="Gradual build over 2 hours, slow energy ramp",
        slots=(
            TemplateSlot(0.00, "ambient_dub", -14.0, 120, 126, 240_000, 0.8),
            TemplateSlot(0.10, "dub_techno", -13.0, 122, 128, 240_000, 0.7),
            TemplateSlot(0.20, "minimal", -11.0, 124, 130, 240_000, 0.6),
            TemplateSlot(0.30, "melodic_deep", -10.0, 126, 132, 240_000, 0.5),
            TemplateSlot(0.40, "progressive", -9.0, 128, 134, 240_000, 0.5),
            TemplateSlot(0.50, "detroit", -8.5, 130, 136, 240_000, 0.4),
            TemplateSlot(0.60, "hypnotic", -8.0, 132, 138, 240_000, 0.4),
            TemplateSlot(0.70, "driving", -7.5, 134, 140, 240_000, 0.3),
            TemplateSlot(0.80, "peak_time", -7.0, 136, 142, 240_000, 0.3),
            TemplateSlot(0.90, "driving", -8.0, 134, 140, 240_000, 0.4),
        ),
    ),
    # ── 6. Wave (120 min) ──────────────────────────────
    "wave_120": SetTemplateDefinition(
        name="wave_120",
        duration_min=120,
        description="Multiple energy waves, build-release-build cycles",
        slots=(
            TemplateSlot(0.00, "minimal", -12.0, 124, 130, 180_000, 0.6),
            TemplateSlot(0.10, "progressive", -9.0, 130, 136, 180_000, 0.5),
            TemplateSlot(0.20, "peak_time", -7.0, 136, 142, 180_000, 0.3),
            TemplateSlot(0.30, "melodic_deep", -10.0, 128, 134, 180_000, 0.6),
            TemplateSlot(0.40, "hypnotic", -9.0, 132, 138, 180_000, 0.4),
            TemplateSlot(0.55, "driving", -7.0, 136, 142, 180_000, 0.3),
            TemplateSlot(0.65, "acid", -6.5, 138, 144, 180_000, 0.3),
            TemplateSlot(0.75, "minimal", -10.0, 128, 134, 180_000, 0.5),
            TemplateSlot(0.85, "peak_time", -7.0, 136, 142, 180_000, 0.3),
            TemplateSlot(0.95, "melodic_deep", -9.0, 128, 134, 180_000, 0.6),
        ),
    ),
    # ── 7. Closing set (60 min) ────────────────────────
    "closing_60": SetTemplateDefinition(
        name="closing_60",
        duration_min=60,
        description="Energy wind-down, graceful ending",
        slots=(
            TemplateSlot(0.00, "driving", -8.0, 132, 138, 180_000, 0.4),
            TemplateSlot(0.15, "hypnotic", -9.0, 130, 136, 180_000, 0.5),
            TemplateSlot(0.30, "melodic_deep", -10.0, 128, 134, 180_000, 0.5),
            TemplateSlot(0.45, "progressive", -11.0, 126, 132, 180_000, 0.5),
            TemplateSlot(0.60, "dub_techno", -12.0, 124, 130, 180_000, 0.6),
            TemplateSlot(0.75, "minimal", -13.0, 122, 128, 180_000, 0.7),
            TemplateSlot(0.90, "ambient_dub", -14.0, 120, 126, 180_000, 0.8),
        ),
    ),
    # ── 8. Full library (variable) ─────────────────────
    "full_library": SetTemplateDefinition(
        name="full_library",
        duration_min=0,
        description="Use all available tracks, optimize ordering only",
        slots=(
            TemplateSlot(0.00, None, -12.0, 120, 140, 300_000, 0.9),
            TemplateSlot(0.25, None, -9.0, 124, 144, 300_000, 0.9),
            TemplateSlot(0.50, None, -7.0, 128, 148, 300_000, 0.9),
            TemplateSlot(0.75, None, -9.0, 124, 144, 300_000, 0.9),
        ),
    ),
}


def get_template(name: str) -> SetTemplateDefinition:
    """Look up template by name. Raises KeyError if not found."""
    return TEMPLATES[name]


def list_template_names() -> list[str]:
    """Return all available template names."""
    return list(TEMPLATES.keys())
