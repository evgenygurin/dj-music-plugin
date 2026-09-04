from __future__ import annotations

from unittest.mock import patch

import pytest

from app.audio.deep import get_runner
from app.config.stems import StemsConfig, detect_runtime


def test_auto_does_not_select_mlx_when_native_backend_missing() -> None:
    with (
        patch("app.config.stems._mlx_available", return_value=False),
        patch("app.config.stems._onnx_available", return_value=True),
    ):
        assert detect_runtime() == "onnx"


def test_auto_prefers_usable_mlx() -> None:
    with patch("app.config.stems._mlx_available", return_value=True):
        assert detect_runtime() == "mlx"


def test_explicit_mlx_does_not_silently_downgrade() -> None:
    cfg = StemsConfig(runtime="mlx")
    with (
        patch("app.audio.deep.demucs_mlx_runner.mlx_backend_available", return_value=False),
        pytest.raises(RuntimeError, match="MLX backend requested"),
    ):
        get_runner(cfg)
