from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.audio.deep.beatgrid_builder import build_beatgrid


def test_build_beatgrid_computes_entry() -> None:
    with (
        patch(
            "app.audio.deep.beatgrid_builder.compute_kick_phase",
            return_value=(0.0, 0.05),
        ),
        patch(
            "app.audio.deep.beatgrid_builder.refine_phase",
            return_value=(0.01, 0.02),
        ),
        patch(
            "app.audio.deep.beatgrid_builder._get_bpm_from_path",
            return_value=130.0,
        ),
    ):
        result = build_beatgrid(Path("/tmp/test.mp3"))

    assert result.bpm == 130.0
    assert result.phase_ms is not None
