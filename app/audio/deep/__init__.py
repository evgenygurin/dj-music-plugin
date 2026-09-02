"""Deep stem separation — 3-tier runtime (mlx → onnx → torch) via StemRunner."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.config.stems import StemRunner, StemsConfig, detect_runtime

# Shared semaphore for M2 8GB — any stem job (resolver or tools/stems) must
# acquire this before touching MPS / unified memory, otherwise two parallel
# graphs OOM on 8GB. Imported by both call-sites.
STEMS_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(1)

__all__ = ["STEMS_SEMAPHORE", "get_runner"]


def get_runner(cfg: StemsConfig | None = None) -> StemRunner:
    """Return best available runner for ``cfg`` (3-tier: mlx → onnx → torch).

    Priority:
    - explicit ``cfg.runtime`` (``mlx`` / ``onnx`` / ``torch`` / ``cpu``) when
      not ``auto`` — attempt that runtime, fallback to next tier if import
      fails;
    - ``auto`` → ``detect_runtime()`` (probes ``mlx.core`` → ``onnxruntime``
      → ``torch`` → ``cpu``).

    All runners expose ``(input_path, cache_root, *, model, flac) -> dict``
    (``StemRunner`` Protocol). ``onnx_separate`` natively has an extra
    ``stems`` param — it is wrapped to request the full 5-stem canonical set
    ``(vocals, drums, bass, harmonic, percussion)`` so cache keys and
    resolver expectations match ``run_demucs`` / ``mlx_separate``.

    Cache: ``sha256(path)[:12] / model / stem.flac`` — not changed.
    """
    if cfg is None:
        cfg = StemsConfig()

    raw = cfg.runtime
    runtime = raw if raw != "auto" else detect_runtime()

    # mlx tier — prefer when available (30x realtime, unified memory)
    if runtime == "mlx":
        try:
            from app.audio.deep.demucs_mlx_runner import mlx_separate

            return mlx_separate
        except Exception:
            # import failed (mlx not installed) → fallback to next tier
            runtime = "onnx"

    # onnx coreml tier — fp16 166MB, Neural Engine → CPU fallback
    if runtime == "onnx":
        try:
            from app.audio.deep.demucs_onnx_runner import onnx_separate

            def _onnx_runner(
                input_path: Path,
                cache_root: Path,
                *,
                model: str | None = None,
                flac: bool = False,
            ) -> dict[str, Path]:
                # request full canonical 5 — default ``("vocals",)`` would
                # yield 1 stem and break resolver's 5-stem check
                return onnx_separate(
                    input_path,
                    cache_root,
                    stems=("vocals", "drums", "bass", "harmonic", "percussion"),
                    model=model,
                    flac=flac,
                )

            _onnx_runner.__name__ = "onnx_separate"
            _onnx_runner.__qualname__ = "onnx_separate"
            return _onnx_runner
        except Exception:
            runtime = "torch"

    # torch mps tier — also serves "cpu" fallback
    if runtime in ("torch", "cpu", "auto"):
        from app.audio.deep.demucs_runner import run_demucs

        return run_demucs

    # unknown string → safest is torch
    from app.audio.deep.demucs_runner import run_demucs

    return run_demucs
