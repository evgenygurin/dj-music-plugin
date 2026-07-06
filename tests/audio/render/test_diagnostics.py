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
