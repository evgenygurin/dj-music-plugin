from __future__ import annotations

from app.models.cross_similarity import CrossSimilarity
from app.models.stem_features import StemFeatures
from app.models.track_embedding import TrackEmbedding
from app.models.track_features import TrackAudioFeaturesComputed, TrackSection


def test_stem_features_has_expected_columns() -> None:
    cols = {c.name for c in StemFeatures.__table__.columns}
    assert "track_id" in cols
    assert "stem_name" in cols
    assert "analysis_level" in cols
    assert "bpm" in cols
    assert "integrated_lufs" in cols
    assert "chords_strength" in cols
    assert "meter" in cols


def test_track_embedding_has_vector_column() -> None:
    cols = {c.name for c in TrackEmbedding.__table__.columns}
    assert "embedding" in cols
    assert "embedding_type" in cols
    assert "stem_name" in cols


def test_cross_similarity_has_expected_columns() -> None:
    cols = {c.name for c in CrossSimilarity.__table__.columns}
    assert "track_a_id" in cols
    assert "track_b_id" in cols
    assert "best_match_offset_ms" in cols
    assert "segment_matches" in cols


def test_analysis_level_check_allows_6() -> None:
    for constraint in TrackAudioFeaturesComputed.__table__.constraints:
        if hasattr(constraint, "sqltext") and "analysis_level" in str(constraint.sqltext):
            assert "6" in str(constraint.sqltext)
            break
    else:
        raise AssertionError("analysis_level CHECK constraint not found")


def test_track_section_has_l6_columns() -> None:
    cols = {c.name for c in TrackSection.__table__.columns}
    assert "lufs" in cols
    assert "spectral_centroid" in cols
    assert "stem_energy" in cols
