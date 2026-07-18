from __future__ import annotations

import pytest

from app.domain.suno_voice.rimjoba import (
    GENRE_TAILS,
    NEGATIVE_TAGS,
    REFERENCE_CLIP_ID,
    VOICE_BLOCK,
    UnknownRimJobaModeError,
    assemble_rimjoba_style,
    list_modes,
)


def test_voice_block_is_immutable_taras_lock() -> None:
    assert "deadpan delivery" in VOICE_BLOCK
    assert "cold cocky" in VOICE_BLOCK
    assert "light autotune" in VOICE_BLOCK
    assert "wide stereo ad-libs" in VOICE_BLOCK
    assert "gang-chant hooks" in VOICE_BLOCK
    assert "no autotune" not in VOICE_BLOCK.lower()


def test_negative_bans_drift() -> None:
    low = NEGATIVE_TAGS.lower()
    for token in ("female vocals", "choir lead", "melodic crooner", "robotic extreme autotune"):
        assert token in low
    assert "no autotune" not in low
    assert "no singing" not in low


def test_all_spec_modes_present() -> None:
    expected = {
        "street_trap",
        "techno_rap",
        "boom_bap",
        "phonk",
        "club",
        "late_night",
    }
    assert set(GENRE_TAILS) == expected
    assert set(list_modes()) == expected


def test_assemble_puts_voice_block_first() -> None:
    prompt = assemble_rimjoba_style("street_trap")
    assert prompt.style.startswith(VOICE_BLOCK)
    assert GENRE_TAILS["street_trap"] in prompt.style
    assert prompt.style.index(VOICE_BLOCK) < prompt.style.index(GENRE_TAILS["street_trap"])
    assert prompt.negative_tags == NEGATIVE_TAGS
    assert prompt.mode == "street_trap"
    assert prompt.title_prefix == "RimJoba"


def test_assemble_extra_negative_appends() -> None:
    prompt = assemble_rimjoba_style("phonk", extra_negative="bright EDM festival drop")
    assert prompt.negative_tags.startswith(NEGATIVE_TAGS)
    assert "bright EDM festival drop" in prompt.negative_tags


def test_assemble_unknown_mode_raises() -> None:
    with pytest.raises(UnknownRimJobaModeError, match="unknown"):
        assemble_rimjoba_style("opera_ballad")


def test_genre_tail_has_no_vocal_identity_words() -> None:
    banned = (
        "deadpan",
        "autotune",
        "baritone",
        "female",
        "choir",
        "crooner",
        "ad-lib",
        "ad lib",
    )
    for mode, tail in GENRE_TAILS.items():
        low = tail.lower()
        for word in banned:
            assert word not in low, f"{mode} tail leaks vocal word: {word}"


def test_reference_clip_id() -> None:
    assert REFERENCE_CLIP_ID == "e4d68e9a-d35d-4e70-8af0-4205cf484d2f"
