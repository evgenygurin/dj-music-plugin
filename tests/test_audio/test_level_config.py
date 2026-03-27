from app.audio.level_config import AnalysisLevel, get_analyzers_for_level, get_clip_duration


def test_level_enum():
    assert AnalysisLevel.NONE == 0
    assert AnalysisLevel.TRIAGE == 2
    assert AnalysisLevel.SCORING == 3
    assert AnalysisLevel.TRANSITION == 4


def test_triage_analyzers():
    names = get_analyzers_for_level(AnalysisLevel.TRIAGE)
    assert set(names) == {"loudness", "energy", "spectral", "bpm", "key", "mfcc"}


def test_scoring_includes_beat_plus_lower():
    names = get_analyzers_for_level(AnalysisLevel.SCORING)
    assert "beat" in names
    assert "loudness" in names
    assert "bpm" in names
    assert len(names) == 7  # 6 from triage + beat


def test_transition_includes_all():
    names = get_analyzers_for_level(AnalysisLevel.TRANSITION)
    assert "structure" in names
    assert "beat" in names
    assert "loudness" in names
    assert len(names) == 8


def test_clip_duration_triage():
    dur = get_clip_duration(AnalysisLevel.TRIAGE)
    assert dur == 30.0


def test_clip_duration_scoring():
    dur = get_clip_duration(AnalysisLevel.SCORING)
    assert dur == 60.0
