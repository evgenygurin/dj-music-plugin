# MLX/Demucs Audio Pipeline Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragile MLX stem-separation path with a correct native `demucs-mlx` backend, eliminate silent failures, and refactor the shared audio pipeline for correctness, observability, cache safety, and Apple Silicon efficiency.

**Architecture:** Keep the existing `StemRunner` compatibility boundary for callers, but move backend-specific inference behind a native MLX `Separator` adapter and isolate audio I/O, canonical stem mapping, derived percussion processing, validation, encoding, and cache persistence. Runtime auto-detection must test backend usability rather than merely `mlx.core` importability; fallback is permitted only for backend availability/capability failures, never for corrupted input, model errors, inference errors, or invalid outputs.

**Tech Stack:** Python 3.12, uv, Pydantic Settings, NumPy, SoundFile, FFmpeg, MLX, demucs-mlx, Demucs/HTDemucs, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-03-mlx-demucs-pipeline-design.md`

## Global Constraints

- Use `uv` for all Python/test/lint/typecheck commands; never invoke pip/python/pytest/ruff/mypy directly.
- Preserve the public `StemRunner` call contract unless a compatibility adapter is required.
- Never convert inference failures or unreadable input into zero-valued audio.
- Native MLX inference must use the current `demucs-mlx` API and avoid unnecessary MLX↔NumPy round trips.
- Canonical output remains `vocals`, `drums`, `bass`, `harmonic`, `percussion`; document `percussion` as derived rather than model-predicted.
- Do not claim a realtime factor without an actual benchmark.
- Keep heavy stem inference serialized by default on the target 8 GB Apple Silicon environment.
- Do not alter system settings or reboot the user's machine.
- Run local verification gates before creating the PR.

---

### Task 1: Establish backend and runtime regression tests

**Files:**
- Modify: `tests/audio/deep/test_mlx_runner.py`
- Create: `tests/audio/deep/test_stems_runtime.py`

**Interfaces:**
- Consumes current `mlx_separate`, `detect_runtime`, `get_runner` contracts.
- Produces regression coverage for missing dependencies, invalid inference, non-silent output, and runtime selection.

- [ ] Write tests proving a mock `Separator` with deterministic non-zero stems produces readable, non-silent output.
- [ ] Write a test proving inference exceptions propagate as `StemInferenceError` (or the final equivalent), never as zero arrays.
- [ ] Write a test proving unreadable input raises an input error.
- [ ] Write runtime tests proving `auto` does not select MLX when only `mlx.core` exists but `demucs_mlx` is unavailable.
- [ ] Write explicit-runtime tests for MLX/ONNX/Torch semantics.
- [ ] Run the focused tests and confirm they fail for the current implementation.

### Task 2: Introduce explicit stem-domain types and error model

**Files:**
- Create: `app/audio/deep/models.py`
- Create: `app/audio/deep/errors.py`
- Modify: `app/config/stems.py`
- Test: `tests/audio/deep/test_stems_models.py`

**Interfaces:**
- `StemSeparationOptions` captures model, segment, overlap, shifts, output format and relevant backend options.
- `StemValidationResult` captures validity and diagnostics.
- Typed errors distinguish unavailable backend, model loading, inference, input, encoding, cache, and output validation failures.

- [ ] Add small immutable/domain-oriented data models without coupling them to a backend.
- [ ] Define fallback classification semantics.
- [ ] Add unit tests for configuration and error classification.
- [ ] Run focused tests.

### Task 3: Implement audio I/O and output validation boundaries

**Files:**
- Create: `app/audio/deep/io.py`
- Create: `app/audio/deep/validation.py`
- Test: `tests/audio/deep/test_audio_io.py`
- Test: `tests/audio/deep/test_stem_validation.py`

**Interfaces:**
- Reader returns normalized stereo audio plus source metadata.
- Writer writes atomically.
- Validator checks existence, decodability, duration, sample rate, channels, finite samples, and silence/pathology conditions.

- [ ] Replace silent zero fallbacks on input errors with explicit exceptions.
- [ ] Normalize mono/stereo and resampling in one place.
- [ ] Make FLAC/WAV writing deterministic and atomic.
- [ ] Add all-zero and near-silent detection that does not reject legitimate quiet stems blindly.
- [ ] Add tests for mono, stereo, non-44.1 kHz, malformed input, NaN/Inf, zero output, and duration mismatch.
- [ ] Run focused tests.

### Task 4: Replace the MLX runner with the native demucs-mlx Separator API

**Files:**
- Modify: `app/audio/deep/demucs_mlx_runner.py`
- Test: `tests/audio/deep/test_mlx_runner.py`

**Interfaces:**
- Preserve `mlx_separate(input_path, cache_root, *, model=None, flac=False) -> dict[str, Path]` for existing callers.
- Internally use the current `demucs_mlx.Separator` API and its native segmentation/overlap/resampling behavior where supported.

- [ ] Lazily import and instantiate `Separator` through a small model factory.
- [ ] Cache/reuse one compatible model instance rather than reloading per track.
- [ ] Pass only supported model/options to the native API; do not invent `separate(chunk)`.
- [ ] Remove the custom duplicated chunk/OLA implementation unless a documented project requirement proves it is still necessary.
- [ ] Keep NumPy conversion at the output boundary only when required by the selected writer.
- [ ] Map native `other` to canonical `harmonic`.
- [ ] Derive `percussion` in an isolated post-processing function if the five-stem contract requires it.
- [ ] Propagate model/inference errors with context.
- [ ] Validate every produced stem before exposing it as successful.
- [ ] Run focused tests.

### Task 5: Refactor runtime detection and runner selection

**Files:**
- Modify: `app/config/stems.py`
- Modify: `app/audio/deep/__init__.py`
- Test: `tests/audio/deep/test_stems_runtime.py`

**Interfaces:**
- Runtime selection distinguishes `auto` from explicit backend selection and availability from usability.

- [ ] Add a cheap backend capability probe for MLX that checks the actual native backend importability.
- [ ] Keep ONNX and Torch fallback behavior compatible with existing callers.
- [ ] Ensure explicit MLX does not silently downgrade on an actual model/inference failure.
- [ ] Ensure auto mode falls back only on availability/capability errors.
- [ ] Avoid importing heavy model packages merely to inspect configuration.
- [ ] Run focused runtime tests.

### Task 6: Align dependencies and lockfile

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` if present
- Test: dependency resolution via `uv sync --all-extras`

**Interfaces:**
- MLX dependencies must be mutually compatible on supported Apple Silicon/Python versions.

- [ ] Inspect current `uv.lock` before changing dependency ranges.
- [ ] Add the actual native Demucs MLX dependency.
- [ ] Pin/constraint MLX and native audio packages to a known-compatible range based on current upstream requirements rather than broad `>=` ranges.
- [ ] Preserve non-darwin and Python-version markers for ONNX/Torch.
- [ ] Resolve with uv and inspect the resulting graph for conflicting native wheels.
- [ ] Run import smoke tests through `uv`.

### Task 7: Refactor cache correctness and atomicity

**Files:**
- Create: `app/audio/deep/cache.py`
- Modify: `app/audio/deep/demucs_mlx_runner.py`
- Test: `tests/audio/deep/test_stem_cache.py`

**Interfaces:**
- Cache identity includes all output-affecting configuration or a stable backend/pipeline version.
- Cache reads are accepted only after output validation.

- [ ] Separate model cache from audio result cache.
- [ ] Preserve existing consumer-facing directory layout where required.
- [ ] Add atomic temp-write/rename behavior.
- [ ] Prevent corrupt/partial outputs from becoming cache hits.
- [ ] Add cache invalidation/version identity for pipeline changes.
- [ ] Test cache hit, cache miss, corrupt artifact, changed model/options, and concurrent access behavior.

### Task 8: Review and refactor canonical percussion derivation

**Files:**
- Create or modify: `app/audio/deep/postprocess.py`
- Test: `tests/audio/deep/test_stem_postprocess.py`

**Interfaces:**
- Native four-stem output is transformed into the stable project-level five-stem contract.

- [ ] Verify downstream consumers actually require five stems.
- [ ] Keep `other -> harmonic` as a semantic mapping.
- [ ] Make percussion derivation explicit and measurable; document that it is not a native model stem.
- [ ] Prefer a deterministic DSP implementation with clear filter behavior over hidden FFmpeg side effects when practical.
- [ ] Add tests for signal energy and reconstruction of the derived drum/percussion split.

### Task 9: Performance and memory profiling

**Files:**
- Review/modify: `app/config/stems.py`
- Review/modify: `app/audio/deep/*`
- Review: `scripts/bench_stems_m2.py`
- Create/modify: `tests/audio/deep/test_mlx_smoke.py`

**Interfaces:**
- Benchmark reports startup, model load, inference, total time, RTF, and memory where measurable.

- [ ] Establish a correctness-first MLX baseline before optimizing.
- [ ] Verify evaluation boundaries using MLX lazy-evaluation guidance.
- [ ] Do not add `mx.compile` until a repeated stable-shape hot path is identified and measured.
- [ ] Benchmark serial inference only initially.
- [ ] Run a short real MLX smoke test on Apple Silicon if dependencies/model are available.
- [ ] Record measured results without hardcoded performance claims.

### Task 10: Documentation and operational guidance

**Files:**
- Modify: `README.md` and relevant `docs/**`
- Create/modify: `docs/superpowers/specs/2026-09-03-mlx-demucs-pipeline-design.md`

**Interfaces:**
- Documentation describes runtime selection, dependencies, model cache, audio validation, troubleshooting, and benchmark commands.

- [ ] Document MLX prerequisites and supported dependency versions.
- [ ] Document explicit versus auto runtime behavior.
- [ ] Document canonical versus native stems.
- [ ] Document failure semantics and diagnostic logging.
- [ ] Document how to run the real MLX smoke test.
- [ ] Document measured benchmark results only.

### Task 11: Full verification and PR preparation

**Files:**
- Modify only files required by previous tasks.

- [ ] Run `uv run ruff check` on the changed scope.
- [ ] Run `uv run mypy` on the changed scope/project as practical.
- [ ] Run focused tests serially while debugging, then the full `uv run pytest` suite.
- [ ] Run import-linter if configured.
- [ ] Inspect the final diff for accidental changes.
- [ ] Verify no silent exception-to-zero paths remain in the stem pipeline.
- [ ] Verify cache artifacts are validated before hit.
- [ ] Verify no secrets or machine-specific paths are committed.
- [ ] Create a concise commit history with independently meaningful commits.
- [ ] Push the branch and open a PR against `main`.
- [ ] PR body must include root cause, architecture changes, tests, benchmark evidence, dependency changes, and remaining risks.
