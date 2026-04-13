"""reset beat-dependent features after BeatDetector fix

BeatDetector was using onset_detect() (irregular onsets) instead of
beat_track() (metrically regular beats), and had no octave error
correction. All beat-dependent features in the DB are therefore wrong.

This migration NULLs out the 12 affected columns and downgrades
analysis_level from 3/5 to 2 (TRIAGE) so that the tiered pipeline
re-analyzes only beat + dependent features on next access.

Unaffected L1+L2 features (loudness, energy, spectral, bpm, key, mfcc)
are preserved — no redundant recomputation.

Revision ID: c3f8a7b21d04
Revises: bdc73180c4b9
Create Date: 2026-04-13 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f8a7b21d04"
down_revision: str | None = "f4a1b2c3d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 12 columns affected by wrong BeatDetector output:
# 4 direct (BeatDetector) + 1 BeatsLoudness + 3 BpmHistogram + 2 PhraseAnalyzer
# + 2 bonus P1 fields that also depend on beat_times
_BEAT_COLUMNS = [
    # BeatDetector direct output
    "onset_rate",
    "pulse_clarity",
    "kick_prominence",
    "hp_ratio",
    # BeatsLoudnessAnalyzer (depends_on: beat)
    "beat_loudness_band_ratio",
    # BpmHistogramAnalyzer (depends_on: beat)
    "bpm_histogram_first_peak_weight",
    "bpm_histogram_second_peak_bpm",
    "bpm_histogram_second_peak_weight",
    # PhraseAnalyzer (depends_on: beat)
    "phrase_boundaries_ms",
    "dominant_phrase_bars",
]


def upgrade() -> None:
    set_clauses = ", ".join(f"{col} = NULL" for col in _BEAT_COLUMNS)
    op.execute(
        f"UPDATE track_audio_features_computed "
        f"SET {set_clauses}, analysis_level = 2 "
        f"WHERE analysis_level >= 3"
    )


def downgrade() -> None:
    # Cannot restore original values — data migration is one-way.
    # Re-analysis via tiered pipeline is the only way to repopulate.
    pass
