from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.audio.deep.demucs_runner import run_demucs


def test_run_demucs_calls_subprocess_with_correct_args() -> None:
    import hashlib
    from app.audio.deep.demucs_runner import _CACHE_ROOT

    input_path = Path("/tmp/test_track.mp3")
    input_path.write_bytes(b"test")  # ensure exists for resolve()
    output_dir = Path("/tmp/demucs_output")

    # Pre-create the cache structure that run_demucs will look for
    cache_key = hashlib.sha256(str(input_path.resolve()).encode()).hexdigest()[:12]
    stem_dir = _CACHE_ROOT / f"test_track_{cache_key}" / "htdemucs" / "test_track"
    stem_dir.mkdir(parents=True, exist_ok=True)
    for name in ("vocals.wav", "drums.wav", "bass.wav", "other.wav"):
        (stem_dir / name).touch()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = run_demucs(input_path, output_dir)

    mock_run.assert_not_called()  # cache hit — no subprocess
    assert result["vocals"] == stem_dir / "vocals.wav"
    assert result["drums"] == stem_dir / "drums.wav"
    assert result["bass"] == stem_dir / "bass.wav"
    assert result["other"] == stem_dir / "other.wav"
    input_path.unlink(missing_ok=True)


def test_run_demucs_raises_on_failure() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        with pytest.raises(RuntimeError, match="Demucs failed to produce"):
            run_demucs(Path("/tmp/test.mp3"), Path("/tmp/out"))
