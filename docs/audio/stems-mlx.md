# Native MLX stem separation

The stem pipeline uses `demucs-mlx` as the Apple Silicon backend when the native backend is actually available.

## Runtime policy

`DJ_STEMS_RUNTIME=auto` probes the complete backend rather than checking only `mlx.core`:

1. MLX + `demucs_mlx`
2. ONNX Runtime
3. Torch
4. CPU/Torch path where supported

An explicitly selected runtime is not silently replaced after inference starts. In `auto`, only backend availability/capability failures are fallbackable. Input decoding, model loading, inference, encoding, and invalid-output failures are surfaced.

## MLX dependencies

The project currently targets the `demucs-mlx` 1.4.x line. As of 2026-09-03, its published compatibility is MLX 0.31.2 with `mlx-audio-io` 1.3.11; the package documentation states that its native audio path does not yet support MLX 0.32. Keep these constraints aligned with the package release before upgrading.

## Native API

The adapter uses:

```python
from demucs_mlx import Separator

separator = Separator(model="htdemucs", shifts=1, overlap=0.25, batch_size=1)
origin, stems = separator.separate_audio_file(path, return_mx=True)
```

`demucs-mlx` owns model-specific resampling and split/overlap-add. The application does not duplicate those algorithms.

## Stem contract

Native HTDemucs produces:

- `vocals`
- `drums`
- `bass`
- `other`

The application exposes:

- `vocals`
- `drums`
- `bass`
- `harmonic` (`other` mapping)
- `percussion` (derived high-frequency portion of `drums`)

`percussion` is not a model prediction.

## Output integrity

A result is published only after the FLAC files can be decoded and pass channel, duration, finite-sample, and non-zero checks. A failed inference is never represented as a zero-filled successful file.

Cache artifacts are validated before being returned as cache hits and are published atomically.

## Performance

MLX uses lazy evaluation and Apple Silicon unified memory. The adapter keeps model inference in MLX and converts to NumPy only at the audio-writing boundary. Heavy inference is serialized by the shared semaphore in the application.

Do not add `mx.compile` or increase batch size without a benchmark. Compilation can recompile when input shapes/types change, and larger batches increase memory pressure.

## Verification

Use the project `uv` workflow. Typical checks:

```bash
uv run pytest tests/audio/deep/test_mlx_runner.py tests/audio/deep/test_stems_runtime.py -n 0
uv run ruff check app/audio/deep app/config/stems.py tests/audio/deep
uv run mypy app/audio/deep app/config/stems.py
```

A real MLX smoke test should be run on Apple Silicon with the `stems` extra installed and a short local audio fixture. Record the measured runtime rather than relying on historical realtime-factor claims.
