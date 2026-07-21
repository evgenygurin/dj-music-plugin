import json

from app.config.render import RenderSettings
from app.domain.render.beatgrid import (
    BeatgridIO,
    BeatgridLimits,
    clamp_entry,
    entry_flags,
    entry_from_row,
    entry_to_row,
)
from app.domain.render.models import BeatgridEntry


def _entry(
    *, trim: float = 0.5, refined: float | None = None, phase: float = 10.0, gain: float = 0.0
) -> BeatgridEntry:
    return BeatgridEntry(
        track_id=1,
        trim_start_s=trim,
        refined_trim_s=refined,
        gain_db=gain,
        phase_ms=phase,
    )


def test_limits_defaults() -> None:
    limits = BeatgridLimits()
    assert limits.max_phase_ms == 120.0
    assert limits.max_trim_start_s == 8.0
    assert limits.fixed_flag_threshold_ms == 40.0
    assert limits.fixed_flag_gain_db == 1.5


def test_clamp_entry_caps_phase_and_trim() -> None:
    limits = BeatgridLimits(max_phase_ms=80.0, max_trim_start_s=8.0)
    entry = _entry(trim=10.0, refined=10.5, phase=200.0)
    clamped = clamp_entry(entry, limits)
    assert clamped.trim_start_s == 8.0
    assert clamped.phase_ms == 80.0
    assert clamped.refined_trim_s == 8.08


def test_clamp_entry_neg_phase_clamped_to_minus_limit() -> None:
    limits = BeatgridLimits(max_phase_ms=120.0)
    entry = _entry(phase=-300.0)
    assert clamp_entry(entry, limits).phase_ms == -120.0


def test_entry_flags_fixed_when_phase_exceeds_threshold() -> None:
    limits = BeatgridLimits(fixed_flag_threshold_ms=40.0, fixed_flag_gain_db=1.5)
    entry = _entry(phase=50.0)
    assert entry_flags(entry, limits) == ["fixed"]


def test_entry_flags_fixed_when_gain_exceeds_threshold() -> None:
    limits = BeatgridLimits(fixed_flag_threshold_ms=40.0, fixed_flag_gain_db=1.5)
    entry = _entry(phase=10.0, gain=2.0)
    assert entry_flags(entry, limits) == ["fixed"]


def test_entry_flags_empty_for_clean_entry() -> None:
    limits = BeatgridLimits()
    entry = _entry(phase=10.0, gain=0.5)
    assert entry_flags(entry, limits) == []


def test_entry_to_row_round_trips() -> None:
    entry = _entry(trim=0.42, refined=0.43, phase=15.0, gain=1.0)
    row = entry_to_row(entry)
    assert row["track_id"] == 1
    assert row["trim_start_s"] == 0.42
    assert row["refined_trim_s"] == 0.43
    assert row["gain_db"] == 1.0
    assert row["phase_ms"] == 15.0
    assert row["flags"] == []


def test_entry_from_row_inverts_to_row() -> None:
    entry = _entry(trim=0.42, refined=0.43, phase=15.0, gain=1.0)
    assert entry_from_row(entry_to_row(entry)) == entry


def test_entry_from_row_ignores_flags() -> None:
    row = entry_to_row(_entry(phase=50.0))
    assert row["flags"] == ["fixed"]
    assert entry_from_row(row) == _entry(phase=50.0)


def test_entry_from_row_handles_missing_refined_and_gain() -> None:
    row = {"track_id": 5, "trim_start_s": 0.4, "phase_ms": 0.0}
    entry = entry_from_row(row)
    assert entry.refined_trim_s is None
    assert entry.gain_db == 0.0


def test_beatgrid_io_write_and_read(tmp_path) -> None:
    entries = [
        _entry(trim=0.4, refined=0.4, phase=0.0),
        _entry(trim=0.5, refined=0.51, phase=10.0, gain=1.5),
    ]
    BeatgridIO.write(str(tmp_path), entries)
    rows = json.loads((tmp_path / "beatgrid.json").read_text())
    assert len(rows) == 2
    assert rows[0]["track_id"] == 1
    assert rows[0]["flags"] == []
    loaded = BeatgridIO.read(str(tmp_path))
    assert loaded == entries


def test_beatgrid_limits_from_settings() -> None:
    settings = RenderSettings()
    limits = BeatgridLimits.from_settings(settings)
    assert limits.max_phase_ms == 120.0
