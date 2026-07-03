"""SetVersionView must tolerate a NULL label (nullable prod column).

Review 2026-07-03 (low): the ORM column ``DjSetVersion.label`` is
nullable but the view declared ``label: str`` — a legacy/raw row with a
NULL label would blow up ``entity_list``/``entity_get`` and the
set-versions relation loader with a pydantic ValidationError.
"""

from __future__ import annotations

from app.models.set import DjSetVersion
from app.schemas.set import SetVersionView


def test_null_label_validates() -> None:
    row = DjSetVersion(id=1, set_id=1, label=None, quality_score=0.5)
    view = SetVersionView.model_validate(row)
    assert view.label is None


def test_regular_label_still_works() -> None:
    row = DjSetVersion(id=2, set_id=1, label="v1", quality_score=0.9)
    assert SetVersionView.model_validate(row).label == "v1"
