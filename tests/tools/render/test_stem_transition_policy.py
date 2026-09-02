"""Tests for dj_stem_transition_policy MCP tool."""

import pytest

from app.tools.render.stem_transition_policy import (
    clear_session_stem_policy,
    get_session_stem_policy,
    merge_session_stem_policy,
    stem_transition_policy,
)


@pytest.fixture(autouse=True)
def reset_policy():
    """Reset session policy before each test."""
    clear_session_stem_policy()
    yield
    clear_session_stem_policy()


@pytest.mark.asyncio
async def test_stem_transition_policy_no_args_returns_empty():
    """Calling with no args returns no applied updates."""
    result = await stem_transition_policy(
        ctx=None,
        vocals_swap_ratio=None,
        harmonic_swap_ratio=None,
        percussion_swap_ratio=None,
        bass_pinpoint_beats=None,
        hpf_overrides=None,
        gain_offsets_db=None,
        fade_curves=None,
        energy_match_db_window=None,
        phrase_alignment=None,
        phrase_snap_window_bars=None,
        vocal_clash_aggression=None,
        transition_length_multiplier=None,
        subgenre=None,
    )
    assert result["applied"] == []
    assert result["policy"] == {}


@pytest.mark.asyncio
async def test_stem_transition_policy_applies_subgenre():
    """Setting subgenre stores it in session policy."""
    result = await stem_transition_policy(
        ctx=None,
        subgenre="hypnotic_techno",
    )
    assert "subgenre" in result["applied"]
    assert get_session_stem_policy()["subgenre"] == "hypnotic_techno"


@pytest.mark.asyncio
async def test_stem_transition_policy_applies_hpf_overrides():
    """Setting hpf_overrides stores dict in session policy."""
    overrides = {"vocals": 150, "percussion": 200}
    await stem_transition_policy(
        ctx=None,
        hpf_overrides=overrides,
    )
    assert get_session_stem_policy()["hpf_overrides"] == overrides


@pytest.mark.asyncio
async def test_merge_session_stem_policy_merges():
    """merge_session_stem_policy merges new kwargs into session."""
    await stem_transition_policy(ctx=None, subgenre="acid_techno")
    merged = merge_session_stem_policy({"hpf_overrides": {"vocals": 100}})
    assert merged["subgenre"] == "acid_techno"
    assert merged["hpf_overrides"] == {"vocals": 100}


@pytest.mark.asyncio
async def test_merge_session_stem_policy_ignores_none_values():
    """merge_session_stem_policy skips None values."""
    await stem_transition_policy(ctx=None, subgenre="acid_techno")
    merged = merge_session_stem_policy({"subgenre": None})
    assert merged["subgenre"] == "acid_techno"


def test_clear_session_stem_policy():
    """clear_session_stem_policy empties the session dict."""
    _SESSION = get_session_stem_policy()
    _SESSION["test"] = 1  # type: ignore[index]
    clear_session_stem_policy()
    assert get_session_stem_policy() == {}
