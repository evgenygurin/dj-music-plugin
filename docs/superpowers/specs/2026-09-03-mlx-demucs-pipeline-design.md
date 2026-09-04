# MLX/Demucs Pipeline Design

## Problem

The existing MLX runner selects MLX when `mlx.core` imports, but attempts a non-current `demucs_mlx.separate` API and can turn missing backends, unreadable input, and inference exceptions into zero-valued audio. That produces technically valid files which are semantically invalid. The runner also duplicates segmentation/overlap-add/resampling already provided by the native MLX backend.

## Decision

Use `demucs-mlx` as the native Apple Silicon inference backend through its `Separator` API. Keep the project's existing `StemRunner` compatibility boundary for callers, but isolate backend inference from audio I/O, canonicalization, post-processing, validation, encoding, and cache persistence.

Runtime selection is capability-based:

```text
auto: MLX backend usable -> ONNX usable -> Torch usable
explicit mlx/onnx/torch: use requested backend; do not silently downgrade inference failures
```

Only backend availability/capability failures are fallbackable in `auto`. Input, model-load, inference, encoding, and output-validation failures are surfaced.

## Native versus canonical stems

Native HTDemucs output is four stems:

```text
vocals / drums / bass / other
```

The application contract remains:

```text
vocals / drums / bass / harmonic / percussion
```

`other` maps to `harmonic`. `percussion` is explicitly a derived post-processing stem, not a model prediction. Its derivation remains isolated and tested. If downstream requirements permit future removal, the native four-stem representation remains the internal source of truth.

## Audio pipeline

```text
Input
  -> AudioReader / decoder
  -> native backend resampling where supported
  -> StemSeparator
  -> canonical stem mapping
  -> optional percussion derivation
  -> AudioWriter
  -> AudioValidator
  -> atomic cache publish
```

The project must not silently replace an invalid input with zeros. Native MLX arrays should remain native until the output boundary where the chosen writer requires NumPy.

## Model lifecycle

A process should reuse one model instance per compatible `(backend, model, relevant options)` rather than reloading weights for every track. Model cache and audio-result cache are distinct concerns.

## MLX evaluation and performance

MLX is lazy and uses Apple Silicon unified memory. Evaluation should occur at useful inference boundaries rather than after every small operation. `mx.compile` is not part of the initial correctness refactor; it may be benchmarked later only for stable repeated shapes. Heavy inference is serialized by default on the target 8 GB environment.

## Cache

Preserve the consumer-facing layout where required. A cache hit is valid only after artifact validation. Output writes are atomic. Cache identity must include a stable pipeline/backend/model identity so changes to output-affecting behavior cannot reuse stale artifacts.

## Validation

Every output must be checked for existence, decodability, expected duration, sample rate/channels, finite samples, and pathological silence. Silence checks must not reject legitimately quiet individual stems solely because RMS is low; all-zero output, zero variance, and cross-stem/source consistency are stronger signals.

## Dependencies

As of 2026-09-03, `demucs-mlx` 1.4.6 documents compatibility with MLX 0.31.2 and `mlx-audio-io` 1.3.11 and states that its native audio package does not yet support MLX 0.32. Therefore the project's MLX dependency must be constrained to a compatible range rather than `mlx>=0.20` without an upper bound. Verify the exact resolver result in `uv.lock` before merge.

## Verification

The change must pass focused tests, full tests, Ruff, mypy where practical, and import-linter if configured. A real MLX smoke test must run on Apple Silicon when the native dependencies and model are available. Performance claims must be based on measured runs, not comments or historical estimates.
