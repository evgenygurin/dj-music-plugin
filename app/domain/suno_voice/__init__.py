"""Suno voice / persona prompt recipes (pure domain)."""

from app.domain.suno_voice.rimjoba import (
    GENRE_TAILS,
    LYRICS_SKELETON,
    NEGATIVE_TAGS,
    REFERENCE_CLIP_ID,
    REFERENCE_URL,
    VOICE_BLOCK,
    RimJobaPrompt,
    UnknownRimJobaModeError,
    assemble_rimjoba_style,
    list_modes,
)

__all__ = [
    "GENRE_TAILS",
    "LYRICS_SKELETON",
    "NEGATIVE_TAGS",
    "REFERENCE_CLIP_ID",
    "REFERENCE_URL",
    "VOICE_BLOCK",
    "RimJobaPrompt",
    "UnknownRimJobaModeError",
    "assemble_rimjoba_style",
    "list_modes",
]
