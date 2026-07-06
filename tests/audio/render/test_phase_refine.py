import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("librosa")


def _click_track(path, bpm=130, sr=22050, dur=26.0, first_kick_s=0.0):
    n = int(sr * dur)
    y = np.zeros(n, dtype="float32")
    beat = 60.0 / bpm
    t = first_kick_s
    while t < dur:
        i = int(t * sr)
        k = int(0.04 * sr)
        env = np.hanning(k)
        y[i : i + k] += (0.9 * env * np.sin(2 * np.pi * 55 * np.arange(k) / sr)).astype("float32")
        t += beat
    sf.write(path, y, sr)
    return path


def test_phase_delta_small_for_ongrid_track(tmp_path):
    from app.audio.render.phase_refine import refine_phase

    f = _click_track(str(tmp_path / "g.wav"), bpm=130, first_kick_s=0.0)
    delta_ms, refined = refine_phase(f, base_trim_s=0.0, bpm=130.0)
    assert abs(delta_ms) < 40.0  # already on grid -> tiny nudge
    assert abs(refined - 0.0) < 0.05
