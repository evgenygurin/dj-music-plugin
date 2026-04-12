from dj_music.audio.level_config import AnalysisLevel, get_analyzers_for_level


def test_level_enum():
    assert AnalysisLevel.NONE == 0
    assert AnalysisLevel.TRIAGE == 2
    assert AnalysisLevel.SCORING == 3
    assert AnalysisLevel.TRANSITION == 4
    assert AnalysisLevel.ADVANCED == 5


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


def test_advanced_includes_p3_plus_lower():
    """ADVANCED level must include all lower-level + 10 P3 analyzers."""
    names = get_analyzers_for_level(AnalysisLevel.ADVANCED)
    # All lower levels included
    assert "loudness" in names  # TRIAGE
    assert "beat" in names  # SCORING
    assert "structure" in names  # TRANSITION
    # All 10 P3 analyzers
    p3 = {
        "danceability",
        "dissonance",
        "dynamic_complexity",
        "spectral_complexity",
        "pitch_salience",
        "tonnetz",
        "tempogram",
        "beats_loudness",
        "bpm_histogram",
        "phrase",
    }
    assert p3.issubset(set(names))
    assert len(names) == 18  # 6 triage + 1 scoring + 1 transition + 10 advanced
