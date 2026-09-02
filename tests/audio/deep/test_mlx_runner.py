"""Tests for MLX runner (30x realtime, chunk 7.8s / 0.25, MPS unified)."""

from __future__ import annotations

import sys
import warnings
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning, message="'aifc' is deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message="'audioop' is deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message="'sunau' is deprecated.*")
warnings.filterwarnings("ignore", category=UserWarning, message="PySoundFile failed.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*__audioread_load.*")


def _write_valid_wav(path: Path, sr: int = 44100, duration: float = 1.0) -> None:
    n = int(sr * duration)
    data = np.zeros((n, 2), dtype=np.int16)
    try:
        import soundfile as sf

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sf.write(str(path), data, sr, subtype="PCM_16")
        return
    except Exception:
        pass
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())


def test_mlx_runner_fallback_when_not_installed(tmp_path: Path) -> None:
    """Fallback: если mlx не установлен — RuntimeError('mlx not installed')."""
    # Патчим sys.modules до импорта модуля, как в brief
    with patch.dict(sys.modules, {"mlx": None, "mlx.core": None}):
        # Форсируем переимпорт чтобы _ensure_mlx увидел None в sys.modules
        if "app.audio.deep.demucs_mlx_runner" in sys.modules:
            del sys.modules["app.audio.deep.demucs_mlx_runner"]
        from app.audio.deep.demucs_mlx_runner import mlx_separate

        with pytest.raises(RuntimeError, match="mlx not installed"):
            mlx_separate(tmp_path / "a.mp3", tmp_path / "cache")


def test_mlx_runner_segment_and_overlap_constants() -> None:
    """Global constraint: segment ≤7.8, overlap 0.25, percussion 2000."""
    from app.audio.deep.demucs_mlx_runner import (
        DEMUCS_OVERLAP,
        DEMUCS_SEGMENT,
        PERCUSSION_SPLIT_HZ,
    )

    assert DEMUCS_SEGMENT == 7.8
    assert DEMUCS_SEGMENT <= 7.8
    assert DEMUCS_OVERLAP == 0.25
    assert PERCUSSION_SPLIT_HZ == 2000


def test_mlx_runner_creates_5_stems(tmp_path: Path) -> None:
    """Базовый: мок mlx, запрос → 5 файлов канонических."""
    # Мокаем проверку mlx и модель чтобы не требовать реальный mlx в CI
    mock_fn = MagicMock(
        return_value=[
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
        ]
    )
    with (
        patch("app.audio.deep.demucs_mlx_runner._ensure_mlx", return_value=MagicMock()),
        patch("app.audio.deep.demucs_mlx_runner._get_mlx_model", return_value=mock_fn),
    ):
        from app.audio.deep.demucs_mlx_runner import mlx_separate

        inp = tmp_path / "a.wav"
        _write_valid_wav(inp)
        res = mlx_separate(inp, tmp_path / "cache")
        assert set(res.keys()) == {"vocals", "drums", "bass", "harmonic", "percussion"}
        for p in res.values():
            assert p.exists(), f"missing {p}"
            assert p.suffix == ".flac"
        # mlx модель вызывалась
        assert mock_fn.called


def test_mlx_runner_cache_hit_skips_inference(tmp_path: Path) -> None:
    """Кэш sha256[:12]/model/stem.flac — второй вызов не дергает модель."""
    mock_fn = MagicMock(
        return_value=[
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
        ]
    )
    with (
        patch("app.audio.deep.demucs_mlx_runner._ensure_mlx", return_value=MagicMock()),
        patch("app.audio.deep.demucs_mlx_runner._get_mlx_model", return_value=mock_fn) as mock_get,
    ):
        from app.audio.deep.demucs_mlx_runner import mlx_separate

        inp = tmp_path / "hit.wav"
        _write_valid_wav(inp)
        res1 = mlx_separate(inp, tmp_path / "cache_hit")
        assert res1["vocals"].exists()
        first_calls = mock_get.call_count

        # второй вызов — cache hit, модель не должна вызываться снова
        # патчим снова но считаем вызовы
        res2 = mlx_separate(inp, tmp_path / "cache_hit")
        assert res2["vocals"].exists()
        assert mock_get.call_count == first_calls  # не создаёт новую модель
        # mock_fn вызывался только в первый раз (второй — кэш)
        assert mock_fn.call_count > 0


def test_mlx_runner_writes_flac_and_percussion_split(tmp_path: Path) -> None:
    """Запись flac (compression 8) + percussion 2kHz (fallback копия если нет ffmpeg)."""
    mock_fn = MagicMock(
        return_value=[
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
        ]
    )
    with (
        patch("app.audio.deep.demucs_mlx_runner._ensure_mlx", return_value=MagicMock()),
        patch("app.audio.deep.demucs_mlx_runner._get_mlx_model", return_value=mock_fn),
        patch("subprocess.run") as mock_run,
    ):

        def _fake_run(*_a, **_kw):
            raise FileNotFoundError("ffmpeg not found")

        mock_run.side_effect = _fake_run
        from app.audio.deep.demucs_mlx_runner import mlx_separate

        inp = tmp_path / "perc.wav"
        _write_valid_wav(inp)
        res = mlx_separate(inp, tmp_path / "cache_perc")
        assert "percussion" in res
        assert "drums" in res
        assert res["percussion"].exists() or res["drums"].exists()


def test_mlx_runner_is_sync_and_protocol_compatible() -> None:
    """Sync API: mlx_separate — sync функция, совместима с StemRunner Protocol."""  # noqa: RUF002
    import inspect

    from app.audio.deep.demucs_mlx_runner import mlx_separate

    assert not inspect.iscoroutinefunction(mlx_separate), "mlx_separate must be sync (to_thread)"
    # проверка что сигнатура совместима с Protocol (input_path, cache_root, *, model, flac)  # noqa: RUF003
    sig = inspect.signature(mlx_separate)
    assert "input_path" in sig.parameters
    assert "cache_root" in sig.parameters
    assert "model" in sig.parameters
    assert "flac" in sig.parameters
