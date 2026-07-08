"""End-to-end measurement + CLI over real synthetic audio.

Exercises the actual decode / BPM / ffmpeg path (no mocking), so it is
skipped unless librosa, soundfile, and ffmpeg are all present.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("librosa")
pytest.importorskip("soundfile")

if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
    pytest.skip("ffmpeg/ffprobe not installed", allow_module_level=True)

import soundfile as sf

from scripts.verify_mix.analysis import collect_measurements, estimate_bpm
from scripts.verify_mix.checks import Status, run_all_checks
from scripts.verify_mix.manifest import parse_manifest

SR = 22050


def _kick_bed(path: Path, bpm: float, dur: float, sr: int = SR) -> None:
    n = int(sr * dur)
    y = np.zeros(n, dtype="float32")
    beat = 60.0 / bpm
    k = int(0.04 * sr)
    env = np.hanning(k).astype("float32")
    t = 0.0
    while t < dur - 0.05:
        i = int(t * sr)
        y[i : i + k] += 0.6 * env * np.sin(2 * np.pi * 55 * np.arange(k) / sr).astype("float32")
        t += beat
    sf.write(path, y, sr)


def _vocal(path: Path, dur: float, freq: float = 700.0, amp: float = 0.5, sr: int = SR) -> None:
    n = int(sr * dur)
    t = np.arange(n) / sr
    # amplitude-modulated tone in the vocal band
    y = (amp * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t)) * np.sin(2 * np.pi * freq * t)).astype(
        "float32"
    )
    sf.write(path, y, sr)


def test_estimate_bpm_recovers_planted_tempo(tmp_path: Path) -> None:
    bed = tmp_path / "bed.wav"
    _kick_bed(bed, bpm=128.0, dur=20.0)
    samples, sr = sf.read(bed)

    bpm, conf = estimate_bpm(samples.astype("float32"), sr)

    # onset-autocorrelation, not a quantized beat_track value
    assert bpm == pytest.approx(128.0, abs=2.0) or bpm == pytest.approx(64.0, abs=2.0)
    assert conf > 0.0


def test_honest_duration_catches_bitrate_lie_is_not_triggered_on_wav(tmp_path: Path) -> None:
    # WAV reports honest duration in both paths → PASS
    bed = tmp_path / "bed.wav"
    _kick_bed(bed, bpm=124.0, dur=12.0)
    manifest = parse_manifest(
        {"output": "mix.wav", "backbone": {"source": "bed.wav", "bpm": 124.0}},
        base_dir=tmp_path,
    )

    m = collect_measurements(manifest, skip_output=True)

    from scripts.verify_mix.checks import VerifyConfig, check_honest_duration

    results = check_honest_duration(manifest, m, VerifyConfig())
    assert results[0].status is Status.PASS


def test_full_pipeline_on_good_mix(tmp_path: Path) -> None:
    bed = tmp_path / "bed.wav"
    vocal = tmp_path / "vocal.wav"
    out = tmp_path / "mix.wav"
    _kick_bed(bed, bpm=124.0, dur=24.0)
    _vocal(vocal, dur=8.0, amp=0.5)

    # render: bed + vocal placed at 4 s, vocal a touch louder in-band
    bed_s, _ = sf.read(bed)
    voc_s, _ = sf.read(vocal)
    mix = bed_s.astype("float32").copy()
    start = int(4.0 * SR)
    seg = min(len(voc_s), len(mix) - start)
    mix[start : start + seg] += voc_s[:seg].astype("float32")
    mix = mix / max(1.0, float(np.max(np.abs(mix))) / 0.9)
    sf.write(out, mix, SR)

    manifest = parse_manifest(
        {
            "output": "mix.wav",
            "backbone": {"source": "bed.wav", "bpm": 124.0},
            "layers": [
                {
                    "source": "vocal.wav",
                    "role": "vocal",
                    "src_trim": [0.0, 8.0],
                    "place_at": 4.0,
                    "gain": 1.0,
                }
            ],
        },
        base_dir=tmp_path,
    )

    m = collect_measurements(manifest)
    results = run_all_checks(manifest, m)

    by_name = {r.name: r for r in results}
    assert by_name["honest_duration"].status is Status.PASS
    assert by_name["clipping"].status is Status.PASS
    assert by_name["dropouts"].status is Status.PASS
    # vocal is at least as loud as the sparse kick bed in-band
    assert by_name["vocal_masking"].status in (Status.PASS, Status.WARN)


def test_cli_exit_code_and_json(tmp_path: Path) -> None:
    from scripts.verify_mix.__main__ import main

    bed = tmp_path / "bed.wav"
    _kick_bed(bed, bpm=124.0, dur=12.0)
    manifest_path = tmp_path / "plan.json"
    manifest_path.write_text(
        json.dumps({"output": "mix.wav", "backbone": {"source": "bed.wav", "bpm": 124.0}}),
        encoding="utf-8",
    )
    json_out = tmp_path / "report.json"

    code = main([str(manifest_path), "--pre-only", "--json", str(json_out)])

    assert code == 0
    payload = json.loads(json_out.read_text())
    assert payload["exit_code"] == 0
    assert {r["name"] for r in payload["results"]} >= {"honest_duration", "bpm_reliability"}
