from __future__ import annotations

from app.models.track_features import TrackSection
from app.schemas.track_section import TrackSectionView


def test_track_section_view_from_orm():
    row = TrackSection(
        id=1,
        track_id=42,
        section_type=3,
        start_ms=32000,
        end_ms=64000,
        energy=0.7,
        stem_energy={"drums": 0.8, "bass": 0.6, "vocals": 0.1, "other": 0.3},
    )
    view = TrackSectionView.model_validate(row)
    assert view.track_id == 42
    assert view.section_type == 3
    assert view.stem_energy == {"drums": 0.8, "bass": 0.6, "vocals": 0.1, "other": 0.3}
