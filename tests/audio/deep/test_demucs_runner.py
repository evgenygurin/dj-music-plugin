from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.audio.deep.demucs_runner import run_demucs


def test_run_demucs_calls_subprocess_with_correct_args() -> None:
    input_path = Path("/tmp/test_track.mp3")
    output_dir = Path("/tmp/demucs_output")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)

        stem_dir = output_dir / "htdemucs" / "test_track"
        stem_dir.mkdir(exist_ok=True, parents=True)
        for name in ("vocals.wav", "drums.wav", "bass.wav", "other.wav"):
            (stem_dir / name).touch()

        result = run_demucs(input_path, output_dir)

    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "python" in args
    assert "-m" in args
    assert "demucs" in args
    assert str(input_path) in args

    assert result["vocals"] == stem_dir / "vocals.wav"
    assert result["drums"] == stem_dir / "drums.wav"
    assert result["bass"] == stem_dir / "bass.wav"
    assert result["other"] == stem_dir / "other.wav"


def test_run_demucs_raises_on_failure() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = RuntimeError("demucs failed")

        with pytest.raises(RuntimeError):
            run_demucs(Path("/tmp/test.mp3"), Path("/tmp/out"))
