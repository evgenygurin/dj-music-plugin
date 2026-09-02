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

    with patch("subprocess.run") as mock_run:
        # When other.wav exists but harmonic.wav doesn't, run_demucs calls
        # subprocess.run(["ffmpeg", ...]) to copy other -> harmonic.
        # Let the real ffmpeg run for this conversion.
        def fake_run(cmd, *args, **kwargs):
            m = MagicMock(returncode=0)
            if cmd and cmd[0] == "ffmpeg" and "-i" in cmd:
                # Allow real ffmpeg to create harmonic.wav from other.wav
                real = subprocess.run(cmd, capture_output=True, check=False)
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
