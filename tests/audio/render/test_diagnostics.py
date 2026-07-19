import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("librosa")


def _mix_with_dropout(path, sr=22050, dur=40.0):
    n = int(sr * dur)
    y = (0.3 * np.random.RandomState(1).randn(n)).astype("float32")
    # inject a near-silent hole 20-24 s
    y[int(20 * sr) : int(24 * sr)] *= 0.02
    sf.write(path, y, sr)
    return path


def test_scan_reports_peak_and_duration(tmp_path):
    from app.audio.render.diagnostics import scan_mix

    f = _mix_with_dropout(str(tmp_path / "m.wav"))
    rep = scan_mix(f)
    assert rep.duration_s >= 39
    assert rep.true_peak_db <= 0.0


def test_diagnose_flags_dropout(tmp_path):
    from app.audio.render.diagnostics import diagnose_mix

    f = _mix_with_dropout(str(tmp_path / "m.wav"))
    rep = diagnose_mix(f)
    tags = [t for w in rep.windows for t in w.tags]
    assert any("DROPOUT" in t for t in tags)


def test_diagnose_flags_phase_instability(tmp_path):
    from app.audio.render.diagnostics import diagnose_mix

    sr = 22050
    dur = 24.0
    n = int(sr * dur)
    rng = np.random.RandomState(2)
    left = (0.15 * rng.randn(n)).astype("float32")
    right = left.copy()
    # Create a strong anti-phase region 8-12s.
    a = int(8 * sr)
    b = int(12 * sr)
    right[a:b] = -left[a:b]
    stereo = np.column_stack([left, right])
    f = str(tmp_path / "phase.wav")
    sf.write(f, stereo, sr)
    rep = diagnose_mix(f)
    tags = [t for w in rep.windows for t in w.tags]
    assert any("PHASE" in t for t in tags)


def test_diagnose_flags_abrupt_entry_shock(tmp_path):
    from app.audio.render.diagnostics import diagnose_mix

    sr = 22050
    dur = 24.0
    n = int(sr * dur)
    rng = np.random.RandomState(3)
    y = np.zeros(n, dtype="float32")
    # low-energy darker bed
    y[: int(8 * sr)] = 0.03 * rng.randn(int(8 * sr))
    # abrupt bright, much louder entry
    y[int(8 * sr) : int(12 * sr)] = 0.35 * rng.randn(int(4 * sr))
    # back to medium energy
    y[int(12 * sr) :] = 0.08 * rng.randn(n - int(12 * sr))
    f = str(tmp_path / "entry.wav")
    sf.write(f, y, sr)
    rep = diagnose_mix(f)
    tags = [t for w in rep.windows for t in w.tags]
    assert any("ENTRY-SHOCK" in t for t in tags)
