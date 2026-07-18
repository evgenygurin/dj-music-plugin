from __future__ import annotations

import pytest

from app.domain.suno_voice.swallow_boy import (
    SWALLOW_BOY_NEGATIVE,
    SWALLOW_BOY_REFERENCE_CLIP_ID,
    SWALLOW_BOY_REFERENCE_URL,
    SWALLOW_BOY_VARIANTS,
    SWALLOW_BOY_VOICE_CORE,
    UnknownSwallowBoyVariantError,
    assemble_swallow_boy_prompt,
    get_swallow_boy_variant,
)


def test_reference_clip_identity() -> None:
    assert SWALLOW_BOY_REFERENCE_CLIP_ID == "ed011c66-bd94-4bb2-bfd8-ec96a78ddc93"
    assert SWALLOW_BOY_REFERENCE_URL.endswith(SWALLOW_BOY_REFERENCE_CLIP_ID)


def test_voice_core_targets_restrained_male_lead() -> None:
    low = SWALLOW_BOY_VOICE_CORE.lower()
    assert "male russian rap lead" in low
    assert "mid-to-low baritone" in low
    assert "close-mic" in low
    assert "restrained confident" in low
    assert "light autotune" in low


def test_negative_excludes_drift_vectors() -> None:
    low = SWALLOW_BOY_NEGATIVE.lower()
    for token in (
        "female lead",
        "choir lead",
        "crooner melisma",
        "opera",
        "heavy robotic autotune",
    ):
        assert token in low


def test_has_exactly_ten_unique_variants() -> None:
    assert len(SWALLOW_BOY_VARIANTS) == 10
    ids = [variant.variant_id for variant in SWALLOW_BOY_VARIANTS]
    assert len(ids) == len(set(ids))


def test_each_variant_has_short_form_lyrics() -> None:
    for variant in SWALLOW_BOY_VARIANTS:
        assert variant.lyrics.strip()
        assert len(variant.lyrics.splitlines()) <= 12
        assert variant.twist.strip()
        assert variant.genre_tail.strip()


def test_assemble_prompt_is_voice_first() -> None:
    prompt = assemble_swallow_boy_prompt("deadpan_baritone")
    assert prompt.style.startswith(SWALLOW_BOY_VOICE_CORE)
    assert "Vocal variant:" in prompt.style
    assert prompt.negative_tags == SWALLOW_BOY_NEGATIVE
    assert prompt.model == "chirp-fenix"
    assert prompt.variant.variant_id == "deadpan_baritone"


def test_get_variant_unknown_raises() -> None:
    with pytest.raises(UnknownSwallowBoyVariantError, match="unknown"):
        get_swallow_boy_variant("does_not_exist")
