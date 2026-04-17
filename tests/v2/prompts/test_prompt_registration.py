"""Prompt metadata constants + registration tests."""

from __future__ import annotations

from app.v2.prompts._shared import PROMPT_META


def test_prompt_meta_has_version() -> None:
    assert "version" in PROMPT_META
    assert "layer" in PROMPT_META
    assert PROMPT_META["layer"] == "prompt"
