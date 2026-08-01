import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("librosa")


def _click_segment(bpm, sr=22050, dur=30.0):
    n = int(sr * dur)
    y = np.zeros(n, dtype="float32")
    beat = 60.0 / bpm
    t = 0.0
    while t < dur:
        i = int(t * sr)
        if i >= n:
            break
        k = min(int(0.04 * sr), n - i)
        env = np.hanning(k)
        y[i : i + k] += (0.9 * env * np.sin(2 * np.pi * 55 * np.arange(k) / sr)).astype("float32")
        t += beat
    return y


def _two_segment_mix(path):
    sr = 22050
    mix = np.concatenate([_click_segment(130.0, sr), _click_segment(131.5, sr)])
    sf.write(path, mix, sr)
    return path


def test_body_windows_with_transitions():
    from app.audio.render.grid_check import body_windows

    segs = [
        {"track_id": 1, "start_s": 0.0, "end_s": 30.0},
        {"track_id": 2, "start_s": 24.0, "end_s": 54.0},
        {"track_id": 3, "start_s": 48.0, "end_s": 78.0},
    ]
    bodies = body_windows(segs)
    assert bodies[1] == (0.0, 24.0)  # d_out = end1 - start2 = 6
    assert bodies[2] == (30.0, 48.0)  # d_in = end1 - start2 = 6; d_out = end2 - start3 = 6
    assert bodies[3] == (54.0, 78.0)  # d_in = end2 - start3 = 6


def test_measure_body_bpm_recovers_target_and_deviation(tmp_path):
    from app.audio.render.grid_check import measure_body_bpm

    f = _two_segment_mix(str(tmp_path / "mix.wav"))
    segs = [
        {"track_id": 1, "start_s": 0.0, "end_s": 30.0},
        {"track_id": 2, "start_s": 30.0, "end_s": 60.0},
    ]
    rows = measure_body_bpm(f, segs, target_bpm=130.0)
    by_id = {r.track_id: r for r in rows}
    assert abs(by_id[1].bpm_measured - 130.0) < 0.5
    assert abs(by_id[2].bpm_measured - 131.5) < 0.5
    assert abs(by_id[1].bpm_dev) < 0.5
    assert 0.5 < by_id[2].bpm_dev < 1.5


def test_classify_grid_status_thresholds():
    from app.audio.render.grid_check import classify_dev

    assert classify_dev(0.0) == "ok"
    assert classify_dev(0.5) == "ok"
    assert classify_dev(0.6) == "warn"
    assert classify_dev(1.0) == "warn"
    assert classify_dev(1.01) == "fail"
