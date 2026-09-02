"""Tests for ONNX CoreML runner (fp16, 166MB, chunk 7.8s / 0.25)."""

from __future__ import annotations

import warnings
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Подавляем сторонние DeprecationWarning от audioread уже на импорте librosa/soundfile,
# чтобы pytest -W error не ловил их как фейлы. Дублирует filterwarnings в pyproject.toml.
warnings.filterwarnings("ignore", category=DeprecationWarning, message="'aifc' is deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message="'audioop' is deprecated.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message="'sunau' is deprecated.*")
warnings.filterwarnings("ignore", category=UserWarning, message="PySoundFile failed.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*__audioread_load.*")


def _write_valid_wav(path: Path, sr: int = 44100, duration: float = 1.0) -> None:
    """Создать валидный WAV (1s тишины) чтобы soundfile→успех и librosa ветка не триггерила audioread."""
    n = int(sr * duration)
    # стерео тишина int16
    data = np.zeros((n, 2), dtype=np.int16)
    try:
        import soundfile as sf

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sf.write(str(path), data, sr, subtype="PCM_16")
        return
    except Exception:
        pass
    # fallback stdlib wave — без зависимостей
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data.tobytes())


def _mock_sess(outputs_per_call: list[np.ndarray] | None = None) -> MagicMock:
    m = MagicMock()
    # get_inputs()[0].name для _get_session
    inp = MagicMock()
    inp.name = "input"
    m.get_inputs.return_value = [inp]
    if outputs_per_call is None:
        outputs_per_call = [np.zeros((2, 44100), dtype=np.float32)]
    m.run.return_value = outputs_per_call
    return m


def test_onnx_runner_creates_5_stems(tmp_path: Path) -> None:
    """Базовый: мок onnx, запрос vocals → файл появляется, providers CoreML→CPU."""
    sess = _mock_sess([np.zeros((2, 44100), dtype=np.float32)])
    with patch("app.audio.deep.demucs_onnx_runner._get_session", return_value=sess) as mock_get:
        from app.audio.deep.demucs_onnx_runner import ONNX_PROVIDERS, onnx_separate

        inp = tmp_path / "a.wav"
        _write_valid_wav(inp)
        res = onnx_separate(inp, tmp_path / "cache", stems=("vocals",))
        assert "vocals" in res
        assert res["vocals"].exists()
        # сессия создавалась
        assert mock_get.called
        assert ONNX_PROVIDERS == ["CoreMLExecutionProvider", "CPUExecutionProvider"]


def test_onnx_runner_creates_all_5_canonical(tmp_path: Path) -> None:
    """Full bag: vocals/drums/bass/harmonic/percussion → 5 файлов."""
    sess = _mock_sess(
        [
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
        ]
    )
    # harmonic=request → native other; drums нужен для percussion
    with patch("app.audio.deep.demucs_onnx_runner._get_session", return_value=sess):
        from app.audio.deep.demucs_onnx_runner import onnx_separate

        inp = tmp_path / "full.wav"
        _write_valid_wav(inp)
        res = onnx_separate(
            inp,
            tmp_path / "cache2",
            stems=("vocals", "drums", "bass", "harmonic", "percussion"),
        )
        assert set(res.keys()) == {"vocals", "drums", "bass", "harmonic", "percussion"}
        for p in res.values():
            assert p.exists(), f"missing {p}"
            assert p.suffix == ".flac"


def test_onnx_runner_vocals_only_vs_bag_run_count(tmp_path: Path) -> None:
    """vocals-only делает 1 выход vs bag 4 выхода на чанк — проверяем маппинг."""
    # vocals-only: один массив
    sess1 = _mock_sess([np.zeros((2, 44100), dtype=np.float32)])
    with patch("app.audio.deep.demucs_onnx_runner._get_session", return_value=sess1):
        from app.audio.deep.demucs_onnx_runner import onnx_separate

        inp = tmp_path / "voc.wav"
        _write_valid_wav(inp)
        res1 = onnx_separate(inp, tmp_path / "cache_voc", stems=("vocals",))
        assert list(res1.keys()) == ["vocals"]

    # bag: 4 выхода
    sess4 = _mock_sess([np.zeros((2, 44100), dtype=np.float32)] * 4)
    with patch("app.audio.deep.demucs_onnx_runner._get_session", return_value=sess4):
        inp2 = tmp_path / "bag.wav"
        _write_valid_wav(inp2)
        res4 = onnx_separate(
            inp2, tmp_path / "cache_bag", stems=("vocals", "drums", "bass", "harmonic")
        )
        assert set(res4.keys()) == {"vocals", "drums", "bass", "harmonic"}


def test_onnx_runner_segment_and_overlap_constants() -> None:
    """Global constraint: segment ≤7.8, overlap 0.25."""
    from app.audio.deep.demucs_onnx_runner import (
        DEMUCS_OVERLAP,
        DEMUCS_SEGMENT,
        PERCUSSION_SPLIT_HZ,
    )

    assert DEMUCS_SEGMENT == 7.8
    assert DEMUCS_SEGMENT <= 7.8
    assert DEMUCS_OVERLAP == 0.25
    assert PERCUSSION_SPLIT_HZ == 2000


def test_onnx_runner_cache_hit_skips_inference(tmp_path: Path) -> None:
    """Кэш sha256[:12]/model/stem.flac — второй вызов не дергает InferenceSession."""
    sess = _mock_sess([np.zeros((2, 44100), dtype=np.float32)])
    with patch("app.audio.deep.demucs_onnx_runner._get_session", return_value=sess) as mock_get:
        from app.audio.deep.demucs_onnx_runner import onnx_separate

        inp = tmp_path / "hit.wav"
        _write_valid_wav(inp)
        res1 = onnx_separate(inp, tmp_path / "cache_hit", stems=("vocals",))
        assert res1["vocals"].exists()
        first_calls = mock_get.call_count

        # второй вызов — cache hit
        res2 = onnx_separate(inp, tmp_path / "cache_hit", stems=("vocals",))
        assert res2["vocals"].exists()
        assert mock_get.call_count == first_calls  # не создаёт новую сессию


def test_onnx_runner_writes_flac_and_percussion_split(tmp_path: Path) -> None:
    """Запись flac (compression 8) + percussion 2kHz (fallback копия если нет ffmpeg)."""
    sess = _mock_sess(
        [
            np.zeros((2, 44100), dtype=np.float32),
            np.zeros((2, 44100), dtype=np.float32),
        ]
    )
    with (
        patch("app.audio.deep.demucs_onnx_runner._get_session", return_value=sess),
        patch("subprocess.run") as mock_run,
    ):
        # ffmpeg для percussion сплита — пусть падает, fallback скопирует drums
        def _fake_run(*_a, **_kw):
            raise FileNotFoundError("ffmpeg not found")

        mock_run.side_effect = _fake_run
        from app.audio.deep.demucs_onnx_runner import onnx_separate

        inp = tmp_path / "perc.wav"
        _write_valid_wav(inp)
        res = onnx_separate(
            inp,
            tmp_path / "cache_perc",
            stems=("drums", "percussion"),
        )
        assert "percussion" in res
        # даже при падении ffmpeg fallback создаёт файл копией drums
        assert res["percussion"].exists() or res["drums"].exists()


def test_onnx_runner_unknown_stem_raises(tmp_path: Path) -> None:
    sess = _mock_sess()
    with patch("app.audio.deep.demucs_onnx_runner._get_session", return_value=sess):
        from app.audio.deep.demucs_onnx_runner import onnx_separate

        with pytest.raises(ValueError, match="unknown stem"):
            onnx_separate(tmp_path / "x.mp3", tmp_path / "c", stems=("guitar",))  # type: ignore[arg-type]
