"""Tests for domain constants and enums."""

from app.core.constants import (
    BPM_MAX,
    BPM_MIN,
    CAMELOT_KEYS,
    CONFIDENCE_MAX,
    CONFIDENCE_MIN,
    DEFAULT_TRANSITION_WEIGHTS,
    ENERGY_MAX,
    ENERGY_MIN,
    HOTCUE_INDEX_MAX,
    HOTCUE_INDEX_MIN,
    KEY_CODE_MAX,
    KEY_CODE_MIN,
    CueKind,
    ExportFormat,
    Provider,
    SectionType,
    SetTemplate,
    TargetApp,
    TechnoSubgenre,
    TrackStatus,
)


def test_track_status_values() -> None:
    assert TrackStatus.ACTIVE == 0
    assert TrackStatus.ARCHIVED == 1


def test_section_types_12() -> None:
    """REQUIREMENTS §10.2: section types 0-11 = 12 values."""
    assert len(SectionType) == 12
    assert SectionType.INTRO == 0
    assert max(SectionType) == 11


def test_cue_kinds_8() -> None:
    """REQUIREMENTS §10.2: cue kinds 0-7 = 8 values."""
    assert len(CueKind) == 8
    assert CueKind.CUE == 0
    assert max(CueKind) == 7


def test_techno_subgenres_count_and_order() -> None:
    subs = list(TechnoSubgenre)
    assert len(subs) == 15
    assert subs[0] == TechnoSubgenre.AMBIENT_DUB
    assert subs[-1] == TechnoSubgenre.HARD_TECHNO


def test_set_templates_8() -> None:
    assert len(SetTemplate) == 8


def test_providers_4() -> None:
    assert len(Provider) == 4


def test_export_formats() -> None:
    assert len(ExportFormat) == 4


def test_target_apps() -> None:
    assert len(TargetApp) == 4


def test_camelot_keys_24_valid() -> None:
    assert len(CAMELOT_KEYS) == 24
    for code, (camelot, _name) in CAMELOT_KEYS.items():
        assert 0 <= code <= 23
        assert camelot[-1] in ("A", "B")
        num = int(camelot[:-1])
        assert 1 <= num <= 12


def test_bpm_constraints() -> None:
    assert BPM_MIN == 20.0
    assert BPM_MAX == 300.0


def test_confidence_constraints() -> None:
    assert CONFIDENCE_MIN == 0.0
    assert CONFIDENCE_MAX == 1.0


def test_energy_constraints() -> None:
    assert ENERGY_MIN == 0.0
    assert ENERGY_MAX == 1.0


def test_key_code_range() -> None:
    assert KEY_CODE_MIN == 0
    assert KEY_CODE_MAX == 23


def test_hotcue_index_range() -> None:
    assert HOTCUE_INDEX_MIN == 0
    assert HOTCUE_INDEX_MAX == 15


def test_transition_weights_sum_and_keys() -> None:
    total = sum(DEFAULT_TRANSITION_WEIGHTS.values())
    assert abs(total - 1.0) < 0.001
    assert set(DEFAULT_TRANSITION_WEIGHTS.keys()) == {
        "bpm",
        "harmonic",
        "energy",
        "spectral",
        "groove",
        "timbral",
    }
