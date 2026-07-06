import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("librosa")


def _click_track(path, bpm=130, sr=22050, dur=24.0, first_kick_s=0.4):
    n = int(sr * dur)
    y = np.zeros(n, dtype="float32")
    beat = 60.0 / bpm
    t = first_kick_s
    while t < dur:
        i = int(t * sr)
        # 40ms low sine burst = a "kick"
        k = int(0.04 * sr)
        env = np.hanning(k)
        y[i : i + k] += (0.9 * env * np.sin(2 * np.pi * 55 * np.arange(k) / sr)).astype("float32")
        t += beat
    sf.write(path, y, sr)
    return path


def test_detect_first_kick(tmp_path):
    from app.audio.render.kick_phase import detect_kick_trim

    f = _click_track(str(tmp_path / "k.wav"), first_kick_s=0.4)
    trim = detect_kick_trim(f, start_s=0.0, bpm=130.0)
    assert 0.30 <= trim <= 0.55  # near the planted 0.4 s kick
