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


def test_analyze_set_flow_simple(tmp_path):
    from app.audio.render.diagnostics import DiagWindow, analyze_set_flow

    windows = [
        DiagWindow(offset_s=0.0, rms_db=-12.0, low_db=-20.0),
        DiagWindow(offset_s=4.0, rms_db=-11.0, low_db=-19.0),
        DiagWindow(offset_s=8.0, rms_db=-10.0, low_db=-18.0),
        DiagWindow(offset_s=12.0, rms_db=-12.0, low_db=-20.0),
        DiagWindow(offset_s=16.0, rms_db=-13.0, low_db=-21.0),
        DiagWindow(offset_s=20.0, rms_db=-12.0, low_db=-22.0),
    ]
    segments = [(1, 0.0, 10.0), (2, 10.0, 20.0)]
    features = {
        1: type(
            "F",
            (),
            {
                "bpm": 128.0,
                "key_code": 8,
                "integrated_lufs": -10.0,
                "energy_mean": 0.4,
                "mood": "driving",
            },
        )(),
        2: type(
            "F",
            (),
            {
                "bpm": 130.0,
                "key_code": 10,
                "integrated_lufs": -9.0,
                "energy_mean": 0.55,
                "mood": "peak_time",
            },
        )(),
    }
    titles = {1: "Track A", 2: "Track B"}

    report = analyze_set_flow("mix.wav", 24.0, windows, segments, features, titles)

    assert report["num_tracks"] == 2
    assert len(report["tracks"]) == 2
    assert len(report["transitions"]) == 1
    assert report["summary"]["camelot_total"] == 1

    t = report["transitions"][0]
    assert t["camelot_compatible"] is True
    assert t["bpm_delta"] == 2.0
    assert t["energy_delta"] == 0.15

    assert report["tracks"][0]["title"] == "Track A"
    assert report["tracks"][1]["title"] == "Track B"


def test_analyze_set_flow_camelot_conflict(tmp_path):
    from app.audio.render.diagnostics import DiagWindow, analyze_set_flow

    windows = [
        DiagWindow(offset_s=float(i * 4), rms_db=-12.0 + i * 0.5, low_db=-20.0) for i in range(8)
    ]
    segments = [(10, 0.0, 16.0), (20, 16.0, 32.0)]
    features = {
        10: type("F", (), {"bpm": 130.0, "key_code": 0, "energy_mean": 0.5})(),
        20: type("F", (), {"bpm": 140.0, "key_code": 22, "energy_mean": 0.7})(),
    }
    titles = {10: "A minor", 20: "Db minor"}

    report = analyze_set_flow("mix.wav", 32.0, windows, segments, features, titles)

    assert report["num_tracks"] == 2
    t = report["transitions"][0]
    assert t["camelot_compatible"] is True
    # 1A (code 0) -> 12A (code 22): distance 1 on wheel (compat)

    # Test with truly incompatible keys
    features2 = {
        10: type("F", (), {"bpm": 130.0, "key_code": 0, "energy_mean": 0.5})(),
        20: type("F", (), {"bpm": 140.0, "key_code": 3, "energy_mean": 0.7})(),
    }
    report2 = analyze_set_flow("mix.wav", 32.0, windows, segments, features2, titles)
    assert report2["transitions"][0]["camelot_compatible"] is True
    # 1A (code 0) -> 2B (code 3): distance 2 (still compatible)

    # Completely incompatible: 1A (code 0) -> 7A (code 12)
    features3 = {
        10: type("F", (), {"bpm": 130.0, "key_code": 0, "energy_mean": 0.5})(),
        20: type("F", (), {"bpm": 140.0, "key_code": 12, "energy_mean": 0.7})(),
    }
    report3 = analyze_set_flow("mix.wav", 32.0, windows, segments, features3, titles)
    assert report3["transitions"][0]["camelot_compatible"] is False
    assert len(report3["warnings"]) >= 1


def test_analyze_set_flow_missing_keys_and_features(tmp_path):
    from app.audio.render.diagnostics import DiagWindow, analyze_set_flow

    windows = [DiagWindow(offset_s=float(i * 4), rms_db=-12.0, low_db=-20.0) for i in range(4)]
    segments = [(1, 0.0, 8.0), (2, 8.0, 16.0)]
    features = {
        1: type("F", (), {"bpm": None, "key_code": None, "energy_mean": None})(),
    }
    titles = {1: "No Feats", 2: "Missing"}

    report = analyze_set_flow("mix.wav", 16.0, windows, segments, features, titles)

    assert report["num_tracks"] == 2
    assert report["tracks"][0]["bpm"] is None
    assert report["tracks"][1]["bpm"] is None
    assert report["transitions"][0]["camelot_compatible"] is None
    assert report["transitions"][0]["bpm_delta"] == 0.0
