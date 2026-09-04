from __future__ import annotations

import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.audio.deep.demucs_mlx_runner import (
    DEMUCS_OVERLAP,
    DEMUCS_SEGMENT,
    PERCUSSION_SPLIT_HZ,
    mlx_separate,
)
from app.audio.deep.errors import AudioInputError, StemInferenceError, StemOutputValidationError


def _write_valid_wav(path: Path, sr: int = 44_100, duration: float = 1.0) -> None:
    n = int(sr * duration)
    t = np.arange(n, dtype=np.float32) / sr
    signal = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    data = np.column_stack((signal, signal))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())


def _separator() -> MagicMock:
    separator = MagicMock()
    separator.samplerate = 44_100
    n = 44_100
    t = np.arange(n, dtype=np.float32) / 44_100
    base = 0.05 * np.sin(2 * np.pi * 440 * t)
    separator.separate_audio_file.return_value = (
        np.vstack((base, base)),
        {
            name: np.vstack((base * scale, base * scale))
            for name, scale in {
                "vocals": 1.0,
                "drums": 0.8,
                "bass": 0.6,
                "other": 0.4,
            }.items()
        },
    )
    return separator


def test_constants() -> None:
    assert DEMUCS_SEGMENT == 7.8
    assert DEMUCS_OVERLAP == 0.25
    assert PERCUSSION_SPLIT_HZ == 2_000


def test_mlx_runner_requires_existing_input(tmp_path: Path) -> None:
    with pytest.raises(AudioInputError, match="does not exist"):
        mlx_separate(tmp_path / "missing.wav", tmp_path / "cache")


def test_mlx_runner_uses_separator_and_creates_five_non_silent_stems(tmp_path: Path) -> None:
    inp = tmp_path / "track.wav"
    _write_valid_wav(inp)
    separator = _separator()

    with patch("app.audio.deep.demucs_mlx_runner._get_separator", return_value=separator):
        result = mlx_separate(inp, tmp_path / "cache")

    assert set(result) == {"vocals", "drums", "bass", "harmonic", "percussion"}
    separator.separate_audio_file.assert_called_once_with(str(inp), return_mx=True)
    for path in result.values():
        assert path.exists()
        import soundfile as sf

        data, sr = sf.read(str(path), always_2d=True, dtype="float32")
        assert sr == 44_100
        assert data.shape[0] == 44_100
        assert np.isfinite(data).all()
        assert float(np.max(np.abs(data))) > 0.0


def test_mlx_runner_propagates_inference_error(tmp_path: Path) -> None:
    inp = tmp_path / "track.wav"
    _write_valid_wav(inp)
    separator = MagicMock()
    separator.separate_audio_file.side_effect = RuntimeError("shape mismatch")

    with (
        patch("app.audio.deep.demucs_mlx_runner._get_separator", return_value=separator),
        pytest.raises(StemInferenceError, match="shape mismatch"),
    ):
        mlx_separate(inp, tmp_path / "cache")


def test_mlx_runner_rejects_all_zero_model_output(tmp_path: Path) -> None:
    inp = tmp_path / "track.wav"
    _write_valid_wav(inp)
    separator = MagicMock()
    zero = np.zeros((2, 44_100), dtype=np.float32)
    separator.samplerate = 44_100
    separator.separate_audio_file.return_value = (
        zero,
        {name: zero for name in ("vocals", "drums", "bass", "other")},
    )

    with (
        patch("app.audio.deep.demucs_mlx_runner._get_separator", return_value=separator),
        pytest.raises(StemOutputValidationError, match="all native stems are zero"),
    ):
        mlx_separate(inp, tmp_path / "cache")


def test_mlx_runner_cache_hit_does_not_infer_again(tmp_path: Path) -> None:
    inp = tmp_path / "track.wav"
    _write_valid_wav(inp)
    separator = _separator()

    with patch("app.audio.deep.demucs_mlx_runner._get_separator", return_value=separator):
        first = mlx_separate(inp, tmp_path / "cache")
        second = mlx_separate(inp, tmp_path / "cache")

    assert first == second
    assert separator.separate_audio_file.call_count == 1
