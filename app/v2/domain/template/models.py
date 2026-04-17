"""DJ set template dataclasses — pure domain data, no I/O."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplateSlot:
    """A single slot in a set template energy arc."""

    position: float  # 0.0-1.0 within set
    target_mood: str | None  # TechnoSubgenre value or None (any)
    energy_lufs: float  # target integrated LUFS
    bpm_min: float
    bpm_max: float
    duration_ms: int  # target duration for this slot
    flexibility: float  # 0.0-1.0, how strict the match


@dataclass(frozen=True, slots=True)
class SetTemplateDefinition:
    """Complete template with metadata and slot sequence."""

    name: str
    duration_min: int
    description: str
    slots: tuple[TemplateSlot, ...]
