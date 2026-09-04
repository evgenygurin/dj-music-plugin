import pytest

from app.domain.analysis.structure import Section


def test_section_represents_typed_interval() -> None:
    section = Section(kind="drop", start_s=32.0, end_s=48.0, confidence=0.92)
    assert section.kind == "drop"
    assert section.duration_s == pytest.approx(16.0)


def test_section_rejects_unknown_kind_and_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="kind"):
        Section(kind="unknown", start_s=0, end_s=1)
    with pytest.raises(ValueError, match="confidence"):
        Section(kind="intro", start_s=0, end_s=1, confidence=2)
