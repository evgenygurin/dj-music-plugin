# ruff: noqa: RUF001

from __future__ import annotations

from app.domain.suno_voice.taras_album import (
    TARAS_ALBUM_TITLE,
    TARAS_ALBUM_TRACKS,
    TARAS_NEGATIVE,
    TARAS_VOICE_CORE,
    assemble_taras_album_prompt,
)


def test_album_title_present() -> None:
    assert "Тарас" in TARAS_ALBUM_TITLE


def test_album_has_eight_tracks() -> None:
    assert len(TARAS_ALBUM_TRACKS) == 8
    assert len({track.slug for track in TARAS_ALBUM_TRACKS}) == 8


def test_voice_core_is_taras_first() -> None:
    low = TARAS_VOICE_CORE.lower()
    assert "low to mid-low baritone" in low
    assert "deadpan" in low
    assert "light autotune" in low


def test_prompt_assembly() -> None:
    track, style, negative = assemble_taras_album_prompt("grafsky_samovar_20")
    assert track.title == "Графский Самовар 2.0"
    assert style.startswith(TARAS_VOICE_CORE)
    assert negative == TARAS_NEGATIVE
