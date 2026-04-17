"""Shared prompt constants."""

from __future__ import annotations

from app import __version__

PROMPT_META: dict[str, str] = {
    "version": __version__,
    "layer": "prompt",
}
