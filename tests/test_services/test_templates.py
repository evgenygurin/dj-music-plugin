"""Tests for DJ set templates — 8 template definitions with slot validation."""

from dj_music.core.constants import SetTemplate
from dj_music.templates.registry import TEMPLATES, get_template, list_template_names

# ── All 8 templates exist ───────────────────────────────


def test_all_eight_templates_exist() -> None:
    assert len(TEMPLATES) == 8


def test_template_names_match_enum() -> None:
    expected = {t.value for t in SetTemplate}
    actual = set(TEMPLATES.keys())
    assert actual == expected


def test_list_template_names() -> None:
    names = list_template_names()
    assert len(names) == 8
    for t in SetTemplate:
        assert t.value in names


def test_get_template_returns_correct() -> None:
    tmpl = get_template("classic_60")
    assert tmpl.name == "classic_60"
    assert tmpl.duration_min == 60


def test_get_template_not_found() -> None:
    raised = False
    try:
        get_template("nonexistent")
    except KeyError:
        raised = True
    assert raised, "Expected KeyError for nonexistent template"


# ── Slot position validation ────────────────────────────


def test_slot_positions_zero_to_one() -> None:
    for name, tmpl in TEMPLATES.items():
        for i, slot in enumerate(tmpl.slots):
            assert 0.0 <= slot.position <= 1.0, (
                f"{name} slot {i}: position {slot.position} out of range"
            )


def test_slot_positions_ascending() -> None:
    for name, tmpl in TEMPLATES.items():
        positions = [s.position for s in tmpl.slots]
        assert positions == sorted(positions), f"{name}: slot positions not ascending: {positions}"


# ── BPM range validation ───────────────────────────────


def test_slot_bpm_ranges_valid() -> None:
    for name, tmpl in TEMPLATES.items():
        for i, slot in enumerate(tmpl.slots):
            assert 120.0 <= slot.bpm_min <= 155.0, (
                f"{name} slot {i}: bpm_min {slot.bpm_min} out of techno range"
            )
            assert 120.0 <= slot.bpm_max <= 155.0, (
                f"{name} slot {i}: bpm_max {slot.bpm_max} out of techno range"
            )
            assert slot.bpm_min <= slot.bpm_max, f"{name} slot {i}: bpm_min > bpm_max"


# ── Energy (LUFS) validation ───────────────────────────


def test_slot_energy_lufs_in_range() -> None:
    for name, tmpl in TEMPLATES.items():
        for i, slot in enumerate(tmpl.slots):
            assert -20.0 <= slot.energy_lufs <= -4.0, (
                f"{name} slot {i}: LUFS {slot.energy_lufs} out of techno range"
            )


# ── Flexibility validation ─────────────────────────────


def test_slot_flexibility_zero_to_one() -> None:
    for name, tmpl in TEMPLATES.items():
        for i, slot in enumerate(tmpl.slots):
            assert 0.0 <= slot.flexibility <= 1.0, (
                f"{name} slot {i}: flexibility {slot.flexibility} out of range"
            )


# ── Duration validation ────────────────────────────────


def test_slot_duration_positive() -> None:
    for name, tmpl in TEMPLATES.items():
        for i, slot in enumerate(tmpl.slots):
            assert slot.duration_ms > 0, f"{name} slot {i}: duration_ms must be positive"


def test_template_duration_min_non_negative() -> None:
    for name, tmpl in TEMPLATES.items():
        assert tmpl.duration_min >= 0, f"{name}: negative duration_min"


# ── Each template has at least 4 slots ──────────────────


def test_templates_have_minimum_slots() -> None:
    for name, tmpl in TEMPLATES.items():
        assert len(tmpl.slots) >= 4, f"{name}: only {len(tmpl.slots)} slots, minimum 4 expected"
