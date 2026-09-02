from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.audio.deep.demucs_runner import run_demucs


def test_run_demucs_returns_canonical_5_stems() -> None:
    """Test that the canonical 5-stem output (vocals/drums/bass/harmonic/percussion) is returned.

    Cache hit: pre-create the canonical files in the demucs output directory
    so run_demucs returns them without invoking Demucs subprocess.
    """
    import hashlib

    input_path = Path("/tmp/test_track.mp3")
    input_path.write_bytes(b"test")
    cache_root = Path("/tmp/demucs_cache")

    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    stem_dir = cache_root / f"test_track_{cache_key}" / "htdemucs" / "test_track"
    stem_dir.mkdir(parents=True, exist_ok=True)
    for name in ("vocals.wav", "drums.wav", "bass.wav", "harmonic.wav", "percussion.wav"):
        (stem_dir / name).touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = run_demucs(input_path, cache_root=cache_root)

    mock_run.assert_not_called()  # cache hit
    assert result["vocals"] == stem_dir / "vocals.wav"
    assert result["drums"] == stem_dir / "drums.wav"
    assert result["bass"] == stem_dir / "bass.wav"
    assert result["harmonic"] == stem_dir / "harmonic.wav"
    assert result["percussion"] == stem_dir / "percussion.wav"
    input_path.unlink(missing_ok=True)


def test_run_demucs_builds_harmonic_from_other_on_cache_miss() -> None:
    """When only Demucs 4-stem output is present, harmonic is built from other.

    Requires ffmpeg for the other→harmonic copy. Skipped when not installed.
    Uses real demucs 4-stem output from the cache as a valid WAV.
    """
    import shutil

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")

    # Generate a real 1-second 440Hz WAV for the test using ffmpeg.
    import subprocess

    src = Path("/tmp/test_other_harmonic_src.wav")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1:sample_rate=44100",
            "-c:a",
            "pcm_s16le",
            str(src),
        ],
        check=True,
        capture_output=True,
    )

    cache_root = Path("/tmp/demucs_other_cache2")
    input_path = src
    import hashlib

    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    stem_dir = cache_root / f"{input_path.stem}_{cache_key}" / "htdemucs" / input_path.stem
    stem_dir.mkdir(parents=True, exist_ok=True)
    # Demucs 4-stem native output; percussion already exists
    for name in ("vocals", "drums", "bass", "other", "percussion"):
        (stem_dir / f"{name}.wav").write_bytes(src.read_bytes())

    # Keep a reference to the real run before patching to avoid recursion
    import subprocess as _subprocess_real

    _real_run = _subprocess_real.run
    with patch("subprocess.run") as mock_run:
        # When other.wav exists but harmonic.wav doesn't, run_demucs calls
        # subprocess.run(["ffmpeg", ...]) to copy other -> harmonic.
        # Let the real ffmpeg run for this conversion.
        def fake_run(cmd, *args, **kwargs):
            m = MagicMock(returncode=0)
            if cmd and cmd[0] == "ffmpeg" and "-i" in cmd:
                # Allow real ffmpeg to create harmonic.wav from other.wav
                real = _real_run(cmd, capture_output=True, check=False)
                m.returncode = real.returncode
                if real.returncode != 0:
                    m.check = True  # would raise
                    raise subprocess.CalledProcessError(real.returncode, cmd, real.stderr)
            return m

        mock_run.side_effect = fake_run
        result = run_demucs(input_path, cache_root=cache_root, model="htdemucs")

    assert result["harmonic"] == stem_dir / "harmonic.wav"
    assert result["percussion"] == stem_dir / "percussion.wav"
    src.unlink(missing_ok=True)


def test_run_demucs_raises_on_failure() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with pytest.raises(RuntimeError, match="Demucs failed to produce"):
            run_demucs(Path("/tmp/test.mp3"), cache_root=Path("/tmp/out"))


def test_stems_config_defaults_m2_8gb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M2 8GB defaults: segment 7.8 (HTDemucs limit), overlap 0.25, jobs 0."""
    monkeypatch.setenv("DJ_STEMS_RUNTIME", "auto")
    # Ensure fresh import after env mutation
    import importlib

    import app.config.stems as stems_mod

    importlib.reload(stems_mod)
    from app.config.stems import StemsConfig

    cfg = StemsConfig()
    assert cfg.segment == 7.8
    assert cfg.overlap == 0.25
    # на 8GB jobs должен быть 0
    assert cfg.jobs == 0


def test_run_demucs_passes_quality_cli_flags(tmp_path: Path) -> None:
    """CLI flags for high-quality separation must be present in the Demucs subprocess call.

    Regression guard for the quality contract: shifts=5 (equivariant stabilization),
    overlap=0.25, segment=7.8 (HTDemucs limit, was 10), clip-mode=rescale, -j adaptive.
    Without these the run is Demucs' lowest-quality mode and SDR drops by ~0.5-0.7 dB per stem.
    """
    import hashlib
    import shutil

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")

    cache_root = tmp_path / "demucs_quality_cache"
    input_path = tmp_path / "test_quality_flags.mp3"
    input_path.write_bytes(b"x")

    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    stem_dir = cache_root / f"test_quality_flags_{cache_key}" / "htdemucs" / "test_quality_flags"
    stem_dir.mkdir(parents=True, exist_ok=True)

    # Now wipe everything to force the Demucs CLI invocation.
    for p in list(stem_dir.iterdir()):
        p.unlink()

    # Capture CLI invocation; mock raw outputs so post-processing can succeed.
    captured: dict[str, list[str] | None] = {"cmd": None}

    def _capture_run(args: list[str], timeout: int = 1800) -> None:  # type: ignore[no-untyped-def]
        captured["cmd"] = list(args)
        # Simulate demucs outputs + canonical stems so post-processing is skipped
        for stem in (
            "vocals.wav",
            "drums.wav",
            "bass.wav",
            "other.wav",
            "harmonic.wav",
            "percussion.wav",
        ):
            (stem_dir / stem).write_bytes(b"RIFF....fake-wav")

    with patch("app.audio.deep.demucs_runner._run_with_retry", side_effect=_capture_run):
        run_demucs(input_path, cache_root=cache_root, model="htdemucs")

    demucs_cmd = captured["cmd"]
    assert demucs_cmd is not None, "Demucs CLI was not invoked"

    # Quality flags must be present in the CLI call.
    from app.audio.deep.demucs_runner import DEMUCS_JOBS, DEMUCS_SEGMENT

    assert "--shifts" in demucs_cmd, f"--shifts missing: {demucs_cmd}"
    assert "5" in demucs_cmd, f"shifts value missing: {demucs_cmd}"
    assert "--overlap" in demucs_cmd
    assert "0.25" in demucs_cmd
    assert "--segment" in demucs_cmd
    # demucs CLI --segment is type=int, so 7.8 → "7" (HTDemucs limit <=7.8)
    assert str(int(DEMUCS_SEGMENT)) in demucs_cmd, (
        f"segment {DEMUCS_SEGMENT} missing: {demucs_cmd}"
    )
    assert DEMUCS_SEGMENT == 7.8, f"segment must be 7.8 on M2 8GB, got {DEMUCS_SEGMENT}"
    assert "--clip-mode" in demucs_cmd
    assert "rescale" in demucs_cmd
    assert "-j" in demucs_cmd
    assert str(DEMUCS_JOBS) in demucs_cmd, f"jobs {DEMUCS_JOBS} missing: {demucs_cmd}"
    assert "-n" in demucs_cmd
    assert "htdemucs" in demucs_cmd

    input_path.unlink(missing_ok=True)
    # Cleanup cache
    import shutil as _shutil

    _shutil.rmtree(cache_root, ignore_errors=True)
